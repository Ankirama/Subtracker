import { useState, useEffect, useRef } from 'react'
import { Link as RouterLink, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Text,
  Button,
  Card,
  CardBody,
  Badge,
  IconButton,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  useToast,
  useDisclosure,
  Icon,
  Divider,
  SimpleGrid,
  Progress,
} from '@chakra-ui/react'
import { FiPlus, FiRefreshCw, FiEdit2, FiTrash2, FiCheckCircle, FiXCircle, FiAlertCircle, FiAlertTriangle, FiLink } from 'react-icons/fi'
import { mailboxesAPI } from '../../api/mailboxes'
import { Mailbox, MailboxSyncStatus } from '../../types'
import { AddMailboxModal } from './AddMailboxModal'
import { SyncEmailsModal } from './SyncEmailsModal'

export const MailboxesPage = () => {
  const [selectedMailbox, setSelectedMailbox] = useState<Mailbox | null>(null)
  const [syncMailbox, setSyncMailbox] = useState<Mailbox | null>(null)
  const [syncingMailboxId, setSyncingMailboxId] = useState<string | null>(null)
  const [syncStatuses, setSyncStatuses] = useState<Map<string, MailboxSyncStatus>>(new Map())
  const pollingIntervalRef = useRef<number | null>(null)
  const { isOpen, onOpen, onClose } = useDisclosure()
  const { isOpen: isSyncOpen, onOpen: onSyncOpen, onClose: onSyncClose } = useDisclosure()
  const [searchParams, setSearchParams] = useSearchParams()

  const queryClient = useQueryClient()
  const toast = useToast()
  const { t } = useTranslation('syncErrors')

  // Handle OAuth callback query params
  useEffect(() => {
    const success = searchParams.get('success')
    const error = searchParams.get('error')

    if (success === 'gmail_connected') {
      toast({
        title: 'Gmail Connected',
        description: 'Your Gmail account has been connected successfully. You can now sync your emails.',
        status: 'success',
        duration: 5000,
        isClosable: true,
      })
      queryClient.invalidateQueries({ queryKey: ['mailboxes'] })
      // Clear the query params
      setSearchParams({})
    } else if (success === 'gmail_updated') {
      toast({
        title: 'Gmail Updated',
        description: 'Your Gmail connection has been updated.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      })
      queryClient.invalidateQueries({ queryKey: ['mailboxes'] })
      setSearchParams({})
    } else if (success === 'gmail_reconnected') {
      toast({
        title: 'Gmail Reconnected',
        description: 'Your Gmail account has been reconnected successfully. You can now sync your emails again.',
        status: 'success',
        duration: 5000,
        isClosable: true,
      })
      queryClient.invalidateQueries({ queryKey: ['mailboxes'] })
      setSearchParams({})
    } else if (error) {
      const errorMessages: Record<string, string> = {
        'invalid_state': 'OAuth session expired. Please try again.',
        'token_exchange_failed': 'Failed to exchange authorization code.',
        'userinfo_failed': 'Failed to get Gmail account information.',
        'no_email': 'Could not retrieve email address from Google.',
        'callback_failed': 'OAuth callback failed. Please try again.',
        'access_denied': 'Access was denied. Please grant Gmail access to continue.',
        'mailbox_not_found': 'Mailbox not found. It may have been deleted.',
      }
      toast({
        title: 'Gmail Connection Failed',
        description: errorMessages[error] || `Error: ${error}`,
        status: 'error',
        duration: 7000,
        isClosable: true,
      })
      setSearchParams({})
    }
  }, [searchParams, setSearchParams, toast, queryClient])

  const { data: mailboxes, isLoading, error } = useQuery({
    queryKey: ['mailboxes'],
    queryFn: mailboxesAPI.getAll,
  })

  // Poll for sync status
  const pollSyncStatus = async (mailboxId: string) => {
    try {
      const status = await mailboxesAPI.getSyncStatus(mailboxId)
      setSyncStatuses(prev => new Map(prev).set(mailboxId, status))

      // Check if sync is complete (including auth_failed which is a terminal state)
      if (status.status === 'success' || status.status === 'failed' || status.status === 'auth_failed') {
        // Stop syncing state
        if (syncingMailboxId === mailboxId) {
          setSyncingMailboxId(null)
        }

        // Show completion notification
        if (status.status === 'success') {
          toast({
            title: 'Sync completed',
            description: `Processed ${status.total_emails_processed || 0} emails, found ${status.subscriptions_found || 0} subscriptions`,
            status: 'success',
            duration: 5000,
            isClosable: true,
          })
        } else if (status.status === 'auth_failed' || status.needs_reconnect) {
          toast({
            title: 'Authentication Required',
            description: 'Your email account needs to be reconnected. Click the Reconnect button to continue.',
            status: 'warning',
            duration: 10000,
            isClosable: true,
          })
        } else if (status.status === 'failed') {
          toast({
            title: 'Sync failed',
            description: status.error_message || 'Unknown error occurred',
            status: 'error',
            duration: 7000,
            isClosable: true,
          })
        }

        // Refresh mailboxes and subscriptions
        queryClient.invalidateQueries({ queryKey: ['mailboxes'] })
        queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
        queryClient.invalidateQueries({ queryKey: ['subscriptionStats'] })

        // Remove from sync statuses
        setSyncStatuses(prev => {
          const newMap = new Map(prev)
          newMap.delete(mailboxId)
          return newMap
        })
      }
    } catch (error) {
      console.error('Failed to poll sync status:', error)
    }
  }

  // Start polling when syncing
  useEffect(() => {
    if (syncingMailboxId) {
      // Poll immediately
      pollSyncStatus(syncingMailboxId)

      // Then poll every 2 seconds
      pollingIntervalRef.current = setInterval(() => {
        pollSyncStatus(syncingMailboxId)
      }, 2000)
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [syncingMailboxId])

  // Check for in-progress syncs on mount
  useEffect(() => {
    if (mailboxes) {
      mailboxes.forEach(mailbox => {
        if (mailbox.last_sync_status === 'in_progress' || mailbox.last_sync_status === 'queued') {
          setSyncingMailboxId(mailbox.id)
        }
      })
    }
  }, [mailboxes])

  const syncMutation = useMutation({
    mutationFn: ({ id, forceFull }: { id: string; forceFull?: boolean }) =>
      mailboxesAPI.sync(id, { force_full_sync: forceFull }),
    onMutate: ({ id }) => {
      setSyncingMailboxId(id)
    },
    onSuccess: (data, { id }) => {
      // Update sync status from response
      setSyncStatuses(prev => new Map(prev).set(id, data))

      toast({
        title: 'Sync started',
        description: 'Email synchronization has been queued',
        status: 'info',
        duration: 3000,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Sync failed',
        description: error.response?.data?.detail || 'Failed to start sync',
        status: 'error',
        duration: 5000,
      })
      setSyncingMailboxId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: mailboxesAPI.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mailboxes'] })
      toast({
        title: 'Mailbox deleted',
        status: 'success',
        duration: 3000,
      })
    },
    onError: () => {
      toast({
        title: 'Failed to delete mailbox',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const handleAddMailbox = () => {
    setSelectedMailbox(null)
    onOpen()
  }

  const handleEdit = (mailbox: Mailbox) => {
    setSelectedMailbox(mailbox)
    onOpen()
  }

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this mailbox? This will not delete synced subscriptions.')) {
      deleteMutation.mutate(id)
    }
  }

  const handleSync = (id: string, forceFull = false) => {
    syncMutation.mutate({ id, forceFull })
  }

  const handleOpenSyncModal = (mailbox: Mailbox) => {
    setSyncMailbox(mailbox)
    onSyncOpen()
  }

  const handleReconnectGoogle = async (mailbox: Mailbox) => {
    try {
      const { authorization_url } = await mailboxesAPI.reconnectGoogle(mailbox.id)
      // Redirect to Google OAuth
      window.location.href = authorization_url
    } catch (error: any) {
      toast({
        title: 'Reconnection Failed',
        description: error.response?.data?.detail || 'Failed to initiate reconnection',
        status: 'error',
        duration: 5000,
        isClosable: true,
      })
    }
  }

  const handleSyncStarted = () => {
    if (syncMailbox) {
      setSyncingMailboxId(syncMailbox.id)
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleString()
  }

  if (isLoading) {
    return (
      <Center h="100vh">
        <Spinner size="xl" color="blue.500" />
      </Center>
    )
  }

  if (error) {
    return (
      <Container maxW="container.xl" py={8}>
        <Alert status="error">
          <AlertIcon />
          Failed to load mailboxes. Please try again.
        </Alert>
      </Container>
    )
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack align="stretch" spacing={6}>
        {/* Header */}
        <HStack justify="space-between">
          <Box>
            <Heading size="lg">Mailboxes</Heading>
            <Text color="text.subtle">
              {mailboxes?.length || 0} connected mailbox{mailboxes?.length !== 1 ? 'es' : ''}
            </Text>
          </Box>
          <Button
            leftIcon={<Icon as={FiPlus} />}
            colorScheme="blue"
            onClick={handleAddMailbox}
          >
            Add Mailbox
          </Button>
        </HStack>

        {/* Mailbox Cards */}
        {mailboxes && mailboxes.length === 0 ? (
          <Card>
            <CardBody>
              <Center py={8}>
                <VStack spacing={4}>
                  <Text fontSize="lg" color="text.subtle">
                    No mailboxes connected yet
                  </Text>
                  <Text color="gray.500">
                    Add a mailbox to start tracking subscriptions from your emails
                  </Text>
                  <Button
                    leftIcon={<Icon as={FiPlus} />}
                    colorScheme="blue"
                    onClick={handleAddMailbox}
                  >
                    Add Your First Mailbox
                  </Button>
                </VStack>
              </Center>
            </CardBody>
          </Card>
        ) : (
          <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
            {mailboxes?.map((mailbox) => (
              <Card key={mailbox.id}>
                <CardBody>
                  <VStack align="stretch" spacing={4}>
                    {/* Header with name and status */}
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1}>
                        <HStack wrap="wrap" spacing={2}>
                          <Heading size="md">{mailbox.display_name || mailbox.email_address}</Heading>
                          <Badge colorScheme={mailbox.is_active ? 'green' : 'gray'}>
                            {mailbox.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                          {mailbox.needs_reconnect && (
                            <Badge colorScheme="orange" variant="solid">
                              <HStack spacing={1}>
                                <Icon as={FiAlertTriangle} boxSize={3} />
                                <Text>Reconnect Required</Text>
                              </HStack>
                            </Badge>
                          )}
                          {mailbox.pending_sync_errors_count > 0 && (
                            <Badge
                              as={RouterLink}
                              to={`/mailboxes/${mailbox.id}/sync-errors`}
                              colorScheme="orange"
                              cursor="pointer"
                              _hover={{ textDecoration: 'underline' }}
                            >
                              {t('badge', { count: mailbox.pending_sync_errors_count })}
                            </Badge>
                          )}
                        </HStack>
                        <Text fontSize="sm" color="text.subtle">
                          {mailbox.email_address}
                        </Text>
                      </VStack>
                      <HStack spacing={2}>
                        <IconButton
                          aria-label="Edit"
                          icon={<Icon as={FiEdit2} />}
                          size="sm"
                          onClick={() => handleEdit(mailbox)}
                        />
                        <IconButton
                          aria-label="Delete"
                          icon={<Icon as={FiTrash2} />}
                          size="sm"
                          colorScheme="red"
                          variant="ghost"
                          onClick={() => handleDelete(mailbox.id)}
                          isLoading={deleteMutation.isPending}
                        />
                      </HStack>
                    </HStack>

                    <Divider />

                    {/* Sync Information */}
                    <VStack align="stretch" spacing={2}>
                      <HStack justify="space-between">
                        <Text fontSize="sm" fontWeight="medium">
                          Last Sync:
                        </Text>
                        <Text fontSize="sm" color="text.subtle">
                          {formatDate(mailbox.last_sync_at)}
                        </Text>
                      </HStack>

                      {mailbox.last_sync_status && (
                        <HStack justify="space-between">
                          <Text fontSize="sm" fontWeight="medium">
                            Sync Status:
                          </Text>
                          <HStack spacing={2}>
                            {(mailbox.last_sync_status === 'in_progress' || mailbox.last_sync_status === 'queued') && (
                              <Spinner size="xs" color="blue.500" />
                            )}
                            <Badge
                              colorScheme={
                                mailbox.last_sync_status === 'completed' || mailbox.last_sync_status === 'success'
                                  ? 'green'
                                  : mailbox.last_sync_status === 'failed'
                                  ? 'red'
                                  : mailbox.last_sync_status === 'auth_failed'
                                  ? 'orange'
                                  : mailbox.last_sync_status === 'running' || mailbox.last_sync_status === 'in_progress' || mailbox.last_sync_status === 'queued'
                                  ? 'blue'
                                  : 'gray'
                              }
                            >
                              {mailbox.last_sync_status === 'auth_failed' ? 'Auth Failed' : mailbox.last_sync_status}
                            </Badge>
                          </HStack>
                        </HStack>
                      )}

                      {/* Show sync progress for in-progress/queued syncs */}
                      {syncStatuses.has(mailbox.id) && (
                        <VStack align="stretch" spacing={1} pt={2}>
                          {syncStatuses.get(mailbox.id)?.status === 'in_progress' && (
                            <>
                              <Progress size="xs" isIndeterminate colorScheme="blue" />
                              <HStack justify="space-between" fontSize="xs" color="text.subtle">
                                <Text>
                                  Emails: {syncStatuses.get(mailbox.id)?.total_emails_processed || 0}
                                </Text>
                                <Text>
                                  Subscriptions: {syncStatuses.get(mailbox.id)?.subscriptions_found || 0}
                                </Text>
                              </HStack>
                            </>
                          )}
                          {syncStatuses.get(mailbox.id)?.status === 'queued' && (
                            <Text fontSize="xs" color="blue.600">
                              Sync queued, waiting to start...
                            </Text>
                          )}
                        </VStack>
                      )}

                      {/* Show last sync metrics */}
                      {mailbox.last_sync_emails_processed !== null && mailbox.last_sync_emails_processed > 0 && (
                        <HStack justify="space-between">
                          <Text fontSize="sm" fontWeight="medium">
                            Last Sync Results:
                          </Text>
                          <HStack spacing={3} fontSize="sm" color="text.subtle">
                            <Text>{mailbox.last_sync_emails_processed} emails</Text>
                            <Text>•</Text>
                            <Text>{mailbox.last_sync_subscriptions_found || 0} subs</Text>
                          </HStack>
                        </HStack>
                      )}

                      {/* Show error message if failed */}
                      {mailbox.last_sync_status === 'failed' && mailbox.last_sync_error_message && !mailbox.needs_reconnect && (
                        <Alert status="error" size="sm" borderRadius="md">
                          <Icon as={FiAlertCircle} mr={2} />
                          <Text fontSize="xs">{mailbox.last_sync_error_message}</Text>
                        </Alert>
                      )}

                      {/* Show auth error if reconnect is needed */}
                      {mailbox.needs_reconnect && (
                        <Alert status="warning" size="sm" borderRadius="md">
                          <AlertIcon />
                          <Box flex="1">
                            <Text fontSize="xs" fontWeight="medium">
                              Authentication expired
                            </Text>
                            <Text fontSize="xs">
                              {mailbox.auth_error_message || 'Please reconnect your Gmail account to continue syncing.'}
                            </Text>
                          </Box>
                        </Alert>
                      )}

                      <HStack justify="space-between">
                        <Text fontSize="sm" fontWeight="medium">
                          Provider:
                        </Text>
                        <Text fontSize="sm" color="text.subtle" textTransform="uppercase">
                          {mailbox.provider_type}
                        </Text>
                      </HStack>

                      <HStack justify="space-between">
                        <Text fontSize="sm" fontWeight="medium">
                          Sync Frequency:
                        </Text>
                        <Text fontSize="sm" color="text.subtle" textTransform="capitalize">
                          {mailbox.sync_frequency}
                        </Text>
                      </HStack>
                    </VStack>

                    <Divider />

                    {/* Sync Actions */}
                    {mailbox.needs_reconnect && mailbox.provider_type === 'gmail' ? (
                      <Button
                        size="sm"
                        leftIcon={<Icon as={FiLink} />}
                        colorScheme="orange"
                        onClick={() => handleReconnectGoogle(mailbox)}
                        w="full"
                      >
                        Reconnect Gmail
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        leftIcon={<Icon as={FiRefreshCw} />}
                        colorScheme="blue"
                        onClick={() => handleOpenSyncModal(mailbox)}
                        isLoading={syncingMailboxId === mailbox.id}
                        isDisabled={!mailbox.is_active || syncingMailboxId !== null || mailbox.needs_reconnect}
                        w="full"
                      >
                        Sync Emails
                      </Button>
                    )}
                  </VStack>
                </CardBody>
              </Card>
            ))}
          </SimpleGrid>
        )}
      </VStack>

      {/* Add/Edit Modal */}
      <AddMailboxModal
        isOpen={isOpen}
        onClose={onClose}
        mailbox={selectedMailbox}
      />

      {/* Sync Modal */}
      <SyncEmailsModal
        isOpen={isSyncOpen}
        onClose={onSyncClose}
        mailbox={syncMailbox}
        onSyncStarted={handleSyncStarted}
      />
    </Container>
  )
}
