import { useState, useEffect, useRef } from 'react'
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
  useColorModeValue,
  FormControl,
  FormLabel,
  Select,
  Flex,
  InputGroup,
  InputRightElement,
  Input,
  Textarea,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Switch,
} from '@chakra-ui/react'
import {
  FiRefreshCw,
  FiCopy,
  FiCheck,
  FiTrash2,
  FiCheckCircle,
  FiXCircle,
  FiUsers,
  FiClock,
  FiChevronLeft,
  FiChevronRight,
} from 'react-icons/fi'
import {
  adminApi,
  WaitlistEntry,
  WaitlistApproveRequest,
  WaitlistRejectRequest,
} from '../../api/admin'

export const AdminWaitlistPage = () => {
  // State
  const [entries, setEntries] = useState<WaitlistEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    approved: 0,
    rejected: 0,
  })

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(20)
  const [totalPages, setTotalPages] = useState(1)
  const [totalEntries, setTotalEntries] = useState(0)

  // Filters
  const [statusFilter, setStatusFilter] = useState<'pending' | 'approved' | 'rejected' | undefined>(undefined)

  // Modals and dialogs
  const { isOpen: isApproveOpen, onOpen: onApproveOpen, onClose: onApproveClose } = useDisclosure()
  const { isOpen: isRejectOpen, onOpen: onRejectOpen, onClose: onRejectClose } = useDisclosure()
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure()

  // Selected entry for actions
  const [selectedEntry, setSelectedEntry] = useState<WaitlistEntry | null>(null)
  const [sendEmail, setSendEmail] = useState(true)
  const [rejectionReason, setRejectionReason] = useState('')
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const cancelRef = useRef<HTMLButtonElement>(null)
  const toast = useToast()
  const bgColor = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  // Load waitlist entries
  const loadWaitlist = async () => {
    try {
      setLoading(true)
      const response = await adminApi.listWaitlist({
        page: currentPage,
        page_size: pageSize,
        status_filter: statusFilter,
      })

      setEntries(response.items)
      setTotalPages(response.total_pages)
      setTotalEntries(response.total)

      // Calculate stats from all entries (not just current page)
      const pending = response.items.filter(e => e.status === 'pending').length
      const approved = response.items.filter(e => e.status === 'approved').length
      const rejected = response.items.filter(e => e.status === 'rejected').length

      setStats({
        total: response.total,
        pending: statusFilter ? pending : response.items.filter(e => e.status === 'pending').length,
        approved: statusFilter ? approved : response.items.filter(e => e.status === 'approved').length,
        rejected: statusFilter ? rejected : response.items.filter(e => e.status === 'rejected').length,
      })
    } catch (error) {
      toast({
        title: 'Error Loading Waitlist',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setLoading(false)
    }
  }

  // Initial load and reload on filters/pagination change
  useEffect(() => {
    loadWaitlist()
  }, [currentPage, statusFilter])

  // Handle approve
  const handleApprove = (entry: WaitlistEntry) => {
    setSelectedEntry(entry)
    setSendEmail(true)
    onApproveOpen()
  }

  const confirmApprove = async () => {
    if (!selectedEntry) return

    try {
      const data: WaitlistApproveRequest = { send_email: sendEmail }
      const response = await adminApi.approveWaitlist(selectedEntry.id, data)

      toast({
        title: 'Approved Successfully',
        description: response.access_code
          ? `Access code: ${response.access_code}`
          : response.message,
        status: 'success',
        duration: 5000,
      })

      onApproveClose()
      loadWaitlist()
    } catch (error: any) {
      toast({
        title: 'Error Approving Entry',
        description: error.response?.data?.detail || 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    }
  }

  // Handle reject
  const handleReject = (entry: WaitlistEntry) => {
    setSelectedEntry(entry)
    setRejectionReason('')
    onRejectOpen()
  }

  const confirmReject = async () => {
    if (!selectedEntry) return

    try {
      const data: WaitlistRejectRequest = { reason: rejectionReason || undefined }
      await adminApi.rejectWaitlist(selectedEntry.id, data)

      toast({
        title: 'Rejected Successfully',
        status: 'success',
        duration: 3000,
      })

      onRejectClose()
      loadWaitlist()
    } catch (error: any) {
      toast({
        title: 'Error Rejecting Entry',
        description: error.response?.data?.detail || 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    }
  }

  // Handle delete
  const handleDelete = (entry: WaitlistEntry) => {
    setSelectedEntry(entry)
    onDeleteOpen()
  }

  const confirmDelete = async () => {
    if (!selectedEntry) return

    try {
      await adminApi.deleteWaitlist(selectedEntry.id)

      toast({
        title: 'Deleted Successfully',
        status: 'success',
        duration: 3000,
      })

      onDeleteClose()
      loadWaitlist()
    } catch (error: any) {
      toast({
        title: 'Error Deleting Entry',
        description: error.response?.data?.detail || 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    }
  }

  // Copy access code to clipboard
  const copyToClipboard = async (entry: WaitlistEntry) => {
    if (!entry.access_code) return

    try {
      await navigator.clipboard.writeText(entry.access_code)
      setCopiedId(entry.id)
      toast({
        title: 'Copied to Clipboard',
        status: 'success',
        duration: 2000,
      })
      setTimeout(() => setCopiedId(null), 2000)
    } catch (error) {
      toast({
        title: 'Failed to Copy',
        status: 'error',
        duration: 2000,
      })
    }
  }

  // Get status badge
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return <Badge colorScheme="yellow">Pending</Badge>
      case 'approved':
        return <Badge colorScheme="green">Approved</Badge>
      case 'rejected':
        return <Badge colorScheme="red">Rejected</Badge>
      default:
        return <Badge>{status}</Badge>
    }
  }

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  if (loading && entries.length === 0) {
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
            <Heading size="lg">Waitlist Management</Heading>
            <Text color="gray.500">Manage access requests and send invitation codes</Text>
          </Box>
          <Button leftIcon={<FiRefreshCw />} variant="outline" onClick={loadWaitlist} isLoading={loading}>
            Refresh
          </Button>
        </HStack>

        {/* Statistics Cards */}
        <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
          <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <FiUsers />
                    <Text>Total Entries</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{stats.total}</StatNumber>
                <StatHelpText>All time</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <FiClock />
                    <Text>Pending</Text>
                  </HStack>
                </StatLabel>
                <StatNumber color="yellow.500">{stats.pending}</StatNumber>
                <StatHelpText>Awaiting review</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <FiCheckCircle />
                    <Text>Approved</Text>
                  </HStack>
                </StatLabel>
                <StatNumber color="green.500">{stats.approved}</StatNumber>
                <StatHelpText>Access granted</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <FiXCircle />
                    <Text>Rejected</Text>
                  </HStack>
                </StatLabel>
                <StatNumber color="red.500">{stats.rejected}</StatNumber>
                <StatHelpText>Access denied</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Filters */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
          <CardBody>
            <HStack spacing={4}>
              <FormControl maxW="300px">
                <FormLabel>Status Filter</FormLabel>
                <Select
                  value={statusFilter || 'all'}
                  onChange={(e) => {
                    const value = e.target.value
                    setStatusFilter(value === 'all' ? undefined : value as 'pending' | 'approved' | 'rejected')
                    setCurrentPage(1)
                  }}
                >
                  <option value="all">All</option>
                  <option value="pending">Pending</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                </Select>
              </FormControl>
            </HStack>
          </CardBody>
        </Card>

        {/* Waitlist Table */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
          <CardBody>
            {loading ? (
              <Center py={10}>
                <Spinner size="xl" />
              </Center>
            ) : entries.length === 0 ? (
              <Center py={10}>
                <Text color="gray.500">No waitlist entries found</Text>
              </Center>
            ) : (
              <Box overflowX="auto">
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Email</Th>
                      <Th>Status</Th>
                      <Th>Access Code</Th>
                      <Th>Created</Th>
                      <Th>Approved</Th>
                      <Th>Rejected</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {entries.map((entry) => (
                      <Tr key={entry.id}>
                        <Td>
                          <Text fontWeight="medium">{entry.email}</Text>
                        </Td>
                        <Td>{getStatusBadge(entry.status)}</Td>
                        <Td>
                          {entry.access_code ? (
                            <HStack>
                              <Text fontFamily="mono" fontSize="sm">
                                {entry.access_code}
                              </Text>
                              <Tooltip label={copiedId === entry.id ? 'Copied!' : 'Copy code'}>
                                <IconButton
                                  aria-label="Copy access code"
                                  icon={copiedId === entry.id ? <FiCheck /> : <FiCopy />}
                                  size="sm"
                                  variant="ghost"
                                  colorScheme={copiedId === entry.id ? 'green' : 'gray'}
                                  onClick={() => copyToClipboard(entry)}
                                />
                              </Tooltip>
                            </HStack>
                          ) : (
                            <Text color="gray.400">-</Text>
                          )}
                        </Td>
                        <Td>
                          <Text fontSize="sm" color="gray.600">
                            {formatDate(entry.created_at)}
                          </Text>
                        </Td>
                        <Td>
                          {entry.approved_at ? (
                            <Text fontSize="sm" color="gray.600">
                              {formatDate(entry.approved_at)}
                            </Text>
                          ) : (
                            <Text color="gray.400">-</Text>
                          )}
                        </Td>
                        <Td>
                          {entry.rejected_at ? (
                            <Text fontSize="sm" color="gray.600">
                              {formatDate(entry.rejected_at)}
                            </Text>
                          ) : (
                            <Text color="gray.400">-</Text>
                          )}
                        </Td>
                        <Td>
                          <HStack spacing={2}>
                            {entry.status === 'pending' && (
                              <>
                                <Tooltip label="Approve and send access code">
                                  <IconButton
                                    aria-label="Approve"
                                    icon={<FiCheckCircle />}
                                    size="sm"
                                    colorScheme="green"
                                    variant="ghost"
                                    onClick={() => handleApprove(entry)}
                                  />
                                </Tooltip>
                                <Tooltip label="Reject entry">
                                  <IconButton
                                    aria-label="Reject"
                                    icon={<FiXCircle />}
                                    size="sm"
                                    colorScheme="orange"
                                    variant="ghost"
                                    onClick={() => handleReject(entry)}
                                  />
                                </Tooltip>
                              </>
                            )}
                            <Tooltip label="Delete entry">
                              <IconButton
                                aria-label="Delete"
                                icon={<FiTrash2 />}
                                size="sm"
                                colorScheme="red"
                                variant="ghost"
                                onClick={() => handleDelete(entry)}
                              />
                            </Tooltip>
                          </HStack>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <Flex justify="space-between" align="center" mt={4}>
                <Text fontSize="sm" color="gray.600">
                  Showing page {currentPage} of {totalPages} ({totalEntries} total entries)
                </Text>
                <HStack spacing={2}>
                  <IconButton
                    aria-label="Previous page"
                    icon={<FiChevronLeft />}
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    isDisabled={currentPage === 1}
                  />
                  <Text fontSize="sm" fontWeight="medium">
                    {currentPage}
                  </Text>
                  <IconButton
                    aria-label="Next page"
                    icon={<FiChevronRight />}
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    isDisabled={currentPage === totalPages}
                  />
                </HStack>
              </Flex>
            )}
          </CardBody>
        </Card>
      </VStack>

      {/* Approve Modal */}
      <Modal isOpen={isApproveOpen} onClose={onApproveClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Approve Waitlist Entry</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Text>
                Are you sure you want to approve <strong>{selectedEntry?.email}</strong>?
              </Text>
              <Text fontSize="sm" color="gray.600">
                An access code will be generated for this user.
              </Text>
              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0" flex="1">
                  Send email with access code
                </FormLabel>
                <Switch isChecked={sendEmail} onChange={(e) => setSendEmail(e.target.checked)} />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onApproveClose}>
              Cancel
            </Button>
            <Button colorScheme="green" onClick={confirmApprove}>
              Approve
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Reject Modal */}
      <Modal isOpen={isRejectOpen} onClose={onRejectClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Reject Waitlist Entry</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Text>
                Are you sure you want to reject <strong>{selectedEntry?.email}</strong>?
              </Text>
              <FormControl>
                <FormLabel>Reason (optional, internal only)</FormLabel>
                <Textarea
                  placeholder="Enter reason for rejection..."
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  rows={3}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onRejectClose}>
              Cancel
            </Button>
            <Button colorScheme="orange" onClick={confirmReject}>
              Reject
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Delete Confirmation Dialog */}
      <AlertDialog isOpen={isDeleteOpen} leastDestructiveRef={cancelRef} onClose={onDeleteClose}>
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Delete Waitlist Entry
            </AlertDialogHeader>
            <AlertDialogBody>
              Are you sure you want to delete {selectedEntry?.email}? This action cannot be undone.
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Cancel
              </Button>
              <Button colorScheme="red" onClick={confirmDelete} ml={3}>
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  )
}
