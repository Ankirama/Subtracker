import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Button,
  VStack,
  HStack,
  Text,
  Select,
  FormControl,
  FormLabel,
  Progress,
  Alert,
  AlertIcon,
  AlertDescription,
  Badge,
  Divider,
  Box,
  NumberInput,
  NumberInputField,
  Icon,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  SimpleGrid,
} from '@chakra-ui/react'
import { FiClock, FiMail, FiCheckCircle, FiAlertCircle } from 'react-icons/fi'
import { mailboxesAPI } from '../../api/mailboxes'
import { Mailbox, MailboxSyncStatus } from '../../types'

interface SyncEmailsModalProps {
  isOpen: boolean
  onClose: () => void
  mailbox: Mailbox | null
  onSyncStarted?: () => void
}

type SyncPeriod = '7days' | '30days' | '90days' | '180days' | '365days' | 'custom'

const PERIOD_OPTIONS: { value: SyncPeriod; label: string; description: string }[] = [
  { value: '7days', label: 'Last 7 days', description: 'Recent emails from the past week' },
  { value: '30days', label: 'Last 30 days', description: 'Default sync period (1 month)' },
  { value: '90days', label: 'Last 90 days', description: 'Last 3 months of emails' },
  { value: '180days', label: 'Last 180 days', description: 'Last 6 months of emails' },
  { value: '365days', label: 'Last 365 days', description: 'Full year of email history' },
  { value: 'custom', label: 'Custom period', description: 'Specify custom number of days' },
]

export const SyncEmailsModal = ({
  isOpen,
  onClose,
  mailbox,
  onSyncStarted,
}: SyncEmailsModalProps) => {
  const [selectedPeriod, setSelectedPeriod] = useState<SyncPeriod>('30days')
  const [customDays, setCustomDays] = useState<string>('60')
  const [syncStatus, setSyncStatus] = useState<MailboxSyncStatus | null>(null)
  const [pollingInterval, setPollingInterval] = useState<ReturnType<typeof setInterval> | null>(null)
  const [startTime, setStartTime] = useState<Date | null>(null)

  const syncMutation = useMutation({
    mutationFn: async () => {
      if (!mailbox) throw new Error('No mailbox selected')

      const dateFilter = selectedPeriod === 'custom'
        ? `${customDays}days`
        : selectedPeriod

      return mailboxesAPI.sync(mailbox.id, {
        force_full_sync: false,
        date_filter_override: dateFilter,
      })
    },
    onSuccess: (data) => {
      setSyncStatus(data)
      setStartTime(new Date())
      onSyncStarted?.()

      // Start polling for status updates
      startPolling()
    },
  })

  const startPolling = () => {
    if (!mailbox) return

    const interval = setInterval(async () => {
      try {
        const status = await mailboxesAPI.getSyncStatus(mailbox.id)
        setSyncStatus(status)

        // Stop polling if sync is complete
        if (status.status === 'success' || status.status === 'failed') {
          clearInterval(interval)
          setPollingInterval(null)
        }
      } catch (error) {
        console.error('Failed to poll sync status:', error)
      }
    }, 2000) // Poll every 2 seconds

    setPollingInterval(interval)
  }

  const handleClose = () => {
    // Clean up polling
    if (pollingInterval) {
      clearInterval(pollingInterval)
      setPollingInterval(null)
    }

    setSyncStatus(null)
    setStartTime(null)
    setSelectedPeriod('30days')
    setCustomDays('60')
    onClose()
  }

  const handleStartSync = () => {
    syncMutation.mutate()
  }

  // Calculate elapsed time
  const getElapsedTime = () => {
    if (!startTime) return '0s'

    const elapsed = Math.floor((Date.now() - startTime.getTime()) / 1000)
    const minutes = Math.floor(elapsed / 60)
    const seconds = elapsed % 60

    if (minutes > 0) {
      return `${minutes}m ${seconds}s`
    }
    return `${seconds}s`
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval)
      }
    }
  }, [pollingInterval])

  const isSyncing = syncStatus?.status === 'in_progress' || syncStatus?.status === 'queued'
  const isComplete = syncStatus?.status === 'success' || syncStatus?.status === 'failed'
  const selectedPeriodInfo = PERIOD_OPTIONS.find(p => p.value === selectedPeriod)

  return (
    <Modal isOpen={isOpen} onClose={handleClose} size="xl" closeOnOverlayClick={!isSyncing}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Sync Emails</ModalHeader>
        {!isSyncing && <ModalCloseButton />}

        <ModalBody>
          <VStack spacing={6} align="stretch">
            {/* Mailbox Info */}
            {mailbox && (
              <Box>
                <Text fontSize="sm" color="text.subtle" mb={1}>Syncing mailbox:</Text>
                <Text fontWeight="semibold">{mailbox.display_name || mailbox.email_address}</Text>
              </Box>
            )}

            {/* Period Selection (only show if not syncing) */}
            {!syncStatus && (
              <>
                <FormControl>
                  <FormLabel>Select Time Period</FormLabel>
                  <Select
                    value={selectedPeriod}
                    onChange={(e) => setSelectedPeriod(e.target.value as SyncPeriod)}
                  >
                    {PERIOD_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                  {selectedPeriodInfo && (
                    <Text fontSize="sm" color="text.subtle" mt={2}>
                      {selectedPeriodInfo.description}
                    </Text>
                  )}
                </FormControl>

                {/* Custom Days Input */}
                {selectedPeriod === 'custom' && (
                  <FormControl>
                    <FormLabel>Number of Days</FormLabel>
                    <NumberInput
                      value={customDays}
                      onChange={setCustomDays}
                      min={1}
                      max={3650}
                    >
                      <NumberInputField placeholder="e.g., 60, 730" />
                    </NumberInput>
                    <Text fontSize="xs" color="text.subtle" mt={1}>
                      Enter 1-3650 days (maximum ~10 years)
                    </Text>
                  </FormControl>
                )}

                <Alert status="info" borderRadius="md">
                  <AlertIcon />
                  <AlertDescription fontSize="sm">
                    <Text fontWeight="semibold" mb={1}>Rate Limiting Info:</Text>
                    <Text>
                      OpenAI API calls are rate-limited to prevent errors.
                      Large syncs may take 10-30 minutes depending on email volume.
                    </Text>
                  </AlertDescription>
                </Alert>
              </>
            )}

            {/* Sync Progress */}
            {syncStatus && (
              <VStack spacing={4} align="stretch">
                <Divider />

                {/* Status Badge */}
                <HStack justify="space-between">
                  <Text fontWeight="semibold">Status:</Text>
                  <Badge
                    colorScheme={
                      syncStatus.status === 'success'
                        ? 'green'
                        : syncStatus.status === 'failed'
                        ? 'red'
                        : syncStatus.status === 'in_progress'
                        ? 'blue'
                        : 'gray'
                    }
                    fontSize="md"
                    px={3}
                    py={1}
                  >
                    {syncStatus.status === 'queued' ? 'Queued' :
                     syncStatus.status === 'in_progress' ? 'In Progress' :
                     syncStatus.status === 'success' ? 'Completed' : 'Failed'}
                  </Badge>
                </HStack>

                {/* Progress Bar */}
                {isSyncing && (
                  <Box>
                    <Progress size="sm" isIndeterminate colorScheme="blue" borderRadius="md" />
                    <Text fontSize="xs" color="text.subtle" mt={1} textAlign="center">
                      Processing emails... This may take several minutes
                    </Text>
                  </Box>
                )}

                {/* Stats */}
                <SimpleGrid columns={2} spacing={4}>
                  <Stat size="sm">
                    <StatLabel>
                      <HStack spacing={1}>
                        <Icon as={FiMail} />
                        <Text>Emails Processed</Text>
                      </HStack>
                    </StatLabel>
                    <StatNumber>{syncStatus.total_emails_processed || 0}</StatNumber>
                  </Stat>

                  <Stat size="sm">
                    <StatLabel>
                      <HStack spacing={1}>
                        <Icon as={FiCheckCircle} />
                        <Text>Subscriptions Found</Text>
                      </HStack>
                    </StatLabel>
                    <StatNumber>{syncStatus.subscriptions_found || 0}</StatNumber>
                  </Stat>
                </SimpleGrid>

                {/* Time Elapsed */}
                {startTime && (
                  <HStack justify="space-between" fontSize="sm">
                    <HStack spacing={1} color="text.subtle">
                      <Icon as={FiClock} />
                      <Text>Time Elapsed:</Text>
                    </HStack>
                    <Text fontWeight="semibold">{getElapsedTime()}</Text>
                  </HStack>
                )}

                {/* Error Message */}
                {syncStatus.status === 'failed' && syncStatus.error_message && (
                  <Alert status="error" borderRadius="md">
                    <Icon as={FiAlertCircle} mr={2} />
                    <AlertDescription fontSize="sm">
                      {syncStatus.error_message}
                    </AlertDescription>
                  </Alert>
                )}

                {/* Success Message */}
                {syncStatus.status === 'success' && (
                  <Alert status="success" borderRadius="md">
                    <AlertIcon />
                    <AlertDescription fontSize="sm">
                      <Text fontWeight="semibold">Sync completed successfully!</Text>
                      <Text mt={1}>
                        Found {syncStatus.subscriptions_found || 0} subscription{syncStatus.subscriptions_found !== 1 ? 's' : ''}
                        {' '}from {syncStatus.total_emails_processed || 0} emails
                      </Text>
                    </AlertDescription>
                  </Alert>
                )}
              </VStack>
            )}
          </VStack>
        </ModalBody>

        <ModalFooter>
          {!syncStatus && (
            <>
              <Button variant="ghost" mr={3} onClick={handleClose}>
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={handleStartSync}
                isLoading={syncMutation.isPending}
              >
                Start Sync
              </Button>
            </>
          )}

          {isSyncing && (
            <Text fontSize="sm" color="text.subtle">
              Syncing in progress... Please wait
            </Text>
          )}

          {isComplete && (
            <Button colorScheme="blue" onClick={handleClose}>
              Close
            </Button>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}
