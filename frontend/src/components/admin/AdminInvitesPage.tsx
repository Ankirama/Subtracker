import { useState, useEffect } from 'react'
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Button,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  IconButton,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Input,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  useDisclosure,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  Card,
  CardBody,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  SimpleGrid,
  Spinner,
  Center,
  Tooltip,
  InputGroup,
  InputRightElement,
  Textarea,
} from '@chakra-ui/react'
import { FiPlus, FiTrash2, FiCopy, FiCheck, FiRefreshCw } from 'react-icons/fi'
import { useRef } from 'react'
import { adminApi, Invite, InviteCreate } from '../../api/admin'

export const AdminInvitesPage = () => {
  const [invites, setInvites] = useState<Invite[]>([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({
    total: 0,
    used: 0,
    pending: 0,
    expired: 0,
  })
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [formData, setFormData] = useState<InviteCreate>({
    email: '',
    note: '',
    expires_in_days: 7,
  })

  const { isOpen, onOpen, onClose } = useDisclosure()
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure()
  const cancelRef = useRef<HTMLButtonElement>(null)
  const toast = useToast()

  const fetchInvites = async () => {
    try {
      setLoading(true)
      const data = await adminApi.listInvites()
      setInvites(data.invites)

      // Calculate stats
      const now = new Date()
      const used = data.invites.filter(i => i.is_used).length
      const expired = data.invites.filter(i => !i.is_used && new Date(i.expires_at) < now).length
      const pending = data.invites.filter(i => !i.is_used && new Date(i.expires_at) >= now).length

      setStats({
        total: data.invites.length,
        used,
        pending,
        expired,
      })
    } catch (error) {
      toast({
        title: 'Failed to load invites',
        status: 'error',
        duration: 3000,
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchInvites()
  }, [])

  const handleCreate = async () => {
    try {
      const invite = await adminApi.createInvite(formData)
      setInvites([invite, ...invites])
      setStats(prev => ({
        ...prev,
        total: prev.total + 1,
        pending: prev.pending + 1,
      }))
      toast({
        title: 'Invite created',
        description: 'The invite link has been created successfully',
        status: 'success',
        duration: 3000,
      })
      onClose()
      setFormData({ email: '', note: '', expires_in_days: 7 })
    } catch (error: any) {
      toast({
        title: 'Failed to create invite',
        description: error.response?.data?.detail || 'An error occurred',
        status: 'error',
        duration: 5000,
      })
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return

    try {
      await adminApi.revokeInvite(deleteId)
      const deletedInvite = invites.find(i => i.id === deleteId)
      setInvites(invites.filter(i => i.id !== deleteId))

      // Update stats
      if (deletedInvite) {
        const now = new Date()
        setStats(prev => ({
          ...prev,
          total: prev.total - 1,
          pending: !deletedInvite.is_used && new Date(deletedInvite.expires_at) >= now
            ? prev.pending - 1
            : prev.pending,
          expired: !deletedInvite.is_used && new Date(deletedInvite.expires_at) < now
            ? prev.expired - 1
            : prev.expired,
        }))
      }

      toast({
        title: 'Invite revoked',
        status: 'success',
        duration: 3000,
      })
    } catch (error: any) {
      toast({
        title: 'Failed to revoke invite',
        description: error.response?.data?.detail || 'An error occurred',
        status: 'error',
        duration: 5000,
      })
    } finally {
      onDeleteClose()
      setDeleteId(null)
    }
  }

  const copyToClipboard = async (invite: Invite) => {
    try {
      await navigator.clipboard.writeText(invite.invite_url)
      setCopiedId(invite.id)
      toast({
        title: 'Copied to clipboard',
        status: 'success',
        duration: 2000,
      })
      setTimeout(() => setCopiedId(null), 2000)
    } catch (error) {
      toast({
        title: 'Failed to copy',
        status: 'error',
        duration: 2000,
      })
    }
  }

  const getStatusBadge = (invite: Invite) => {
    if (invite.is_used) {
      return <Badge colorScheme="green">Used</Badge>
    }
    const now = new Date()
    if (new Date(invite.expires_at) < now) {
      return <Badge colorScheme="red">Expired</Badge>
    }
    return <Badge colorScheme="blue">Pending</Badge>
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  if (loading) {
    return (
      <Center h="400px">
        <Spinner size="xl" color="red.500" />
      </Center>
    )
  }

  return (
    <Box>
      <VStack align="stretch" spacing={6}>
        {/* Header */}
        <HStack justify="space-between">
          <Box>
            <Heading size="lg">Invite Management</Heading>
            <Text color="gray.500">Create and manage user invitation tokens</Text>
          </Box>
          <HStack>
            <Button
              leftIcon={<FiRefreshCw />}
              variant="outline"
              onClick={fetchInvites}
            >
              Refresh
            </Button>
            <Button
              leftIcon={<FiPlus />}
              colorScheme="red"
              onClick={onOpen}
            >
              Create Invite
            </Button>
          </HStack>
        </HStack>

        {/* Stats */}
        <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Total Invites</StatLabel>
                <StatNumber>{stats.total}</StatNumber>
                <StatHelpText>All time</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Pending</StatLabel>
                <StatNumber color="blue.500">{stats.pending}</StatNumber>
                <StatHelpText>Awaiting use</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Used</StatLabel>
                <StatNumber color="green.500">{stats.used}</StatNumber>
                <StatHelpText>Successfully registered</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Expired</StatLabel>
                <StatNumber color="red.500">{stats.expired}</StatNumber>
                <StatHelpText>Not used in time</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Invites Table */}
        <Card>
          <CardBody>
            {invites.length === 0 ? (
              <Center py={8}>
                <VStack spacing={4}>
                  <Text color="gray.500">No invites created yet</Text>
                  <Button leftIcon={<FiPlus />} colorScheme="red" onClick={onOpen}>
                    Create First Invite
                  </Button>
                </VStack>
              </Center>
            ) : (
              <Table variant="simple">
                <Thead>
                  <Tr>
                    <Th>Email</Th>
                    <Th>Status</Th>
                    <Th>Created</Th>
                    <Th>Expires</Th>
                    <Th>Note</Th>
                    <Th>Actions</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {invites.map((invite) => (
                    <Tr key={invite.id}>
                      <Td>
                        <Text fontWeight="medium">
                          {invite.invited_email || '(Any email)'}
                        </Text>
                      </Td>
                      <Td>{getStatusBadge(invite)}</Td>
                      <Td>
                        <Text fontSize="sm" color="gray.600">
                          {formatDate(invite.created_at)}
                        </Text>
                      </Td>
                      <Td>
                        <Text fontSize="sm" color="gray.600">
                          {formatDate(invite.expires_at)}
                        </Text>
                      </Td>
                      <Td>
                        <Text fontSize="sm" color="gray.600" maxW="200px" isTruncated>
                          {invite.note || '-'}
                        </Text>
                      </Td>
                      <Td>
                        <HStack spacing={2}>
                          <Tooltip label={copiedId === invite.id ? 'Copied!' : 'Copy invite URL'}>
                            <IconButton
                              aria-label="Copy invite URL"
                              icon={copiedId === invite.id ? <FiCheck /> : <FiCopy />}
                              size="sm"
                              colorScheme={copiedId === invite.id ? 'green' : 'gray'}
                              variant="ghost"
                              onClick={() => copyToClipboard(invite)}
                              isDisabled={invite.is_used}
                            />
                          </Tooltip>
                          <Tooltip label="Revoke invite">
                            <IconButton
                              aria-label="Revoke invite"
                              icon={<FiTrash2 />}
                              size="sm"
                              colorScheme="red"
                              variant="ghost"
                              onClick={() => {
                                setDeleteId(invite.id)
                                onDeleteOpen()
                              }}
                              isDisabled={invite.is_used}
                            />
                          </Tooltip>
                        </HStack>
                      </Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            )}
          </CardBody>
        </Card>
      </VStack>

      {/* Create Invite Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create New Invite</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Email (optional)</FormLabel>
                <Input
                  type="email"
                  placeholder="user@example.com"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                />
                <Text fontSize="xs" color="gray.500" mt={1}>
                  Leave empty to allow any email to use this invite
                </Text>
              </FormControl>

              <FormControl>
                <FormLabel>Expires in (days)</FormLabel>
                <NumberInput
                  min={1}
                  max={90}
                  value={formData.expires_in_days}
                  onChange={(_, value) => setFormData({ ...formData, expires_in_days: value || 7 })}
                >
                  <NumberInputField />
                  <NumberInputStepper>
                    <NumberIncrementStepper />
                    <NumberDecrementStepper />
                  </NumberInputStepper>
                </NumberInput>
              </FormControl>

              <FormControl>
                <FormLabel>Note (optional)</FormLabel>
                <Textarea
                  placeholder="Internal note about this invite..."
                  value={formData.note}
                  onChange={(e) => setFormData({ ...formData, note: e.target.value })}
                  rows={3}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button colorScheme="red" onClick={handleCreate}>
              Create Invite
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        isOpen={isDeleteOpen}
        leastDestructiveRef={cancelRef}
        onClose={onDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Revoke Invite
            </AlertDialogHeader>
            <AlertDialogBody>
              Are you sure you want to revoke this invite? This action cannot be undone.
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Cancel
              </Button>
              <Button colorScheme="red" onClick={handleDelete} ml={3}>
                Revoke
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  )
}
