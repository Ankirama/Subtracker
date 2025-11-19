import { useState, useEffect, useRef } from 'react'
import {
  Box,
  Button,
  Heading,
  VStack,
  HStack,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  useToast,
  Card,
  CardBody,
  Text,
  Badge,
  useColorModeValue,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  IconButton,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  useDisclosure,
  Spinner,
  Center,
  Flex,
  Tooltip,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
} from '@chakra-ui/react'
import {
  FiShield,
  FiPlus,
  FiEdit2,
  FiTrash2,
  FiChevronsLeft,
  FiChevronLeft,
  FiChevronRight,
  FiChevronsRight,
  FiRefreshCw,
} from 'react-icons/fi'
import {
  adminApi,
  type IPWhitelistEntry,
} from '../../api/admin'

export const AdminIPWhitelistPage = () => {
  // State
  const [entries, setEntries] = useState<IPWhitelistEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(20)
  const [totalPages, setTotalPages] = useState(1)
  const [totalEntries, setTotalEntries] = useState(0)

  // Form state
  const [newIpAddress, setNewIpAddress] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [editEntry, setEditEntry] = useState<IPWhitelistEntry | null>(null)
  const [editDescription, setEditDescription] = useState('')

  // Modals
  const { isOpen: isAddOpen, onOpen: onAddOpen, onClose: onAddClose } = useDisclosure()
  const { isOpen: isEditOpen, onOpen: onEditOpen, onClose: onEditClose } = useDisclosure()
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure()
  const [entryToDelete, setEntryToDelete] = useState<IPWhitelistEntry | null>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)

  const toast = useToast()
  const bgColor = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  // Load entries
  const loadEntries = async () => {
    try {
      setIsLoading(true)
      const response = await adminApi.listIPWhitelist({
        page: currentPage,
        page_size: pageSize,
      })
      setEntries(response.items)
      setTotalPages(response.total_pages)
      setTotalEntries(response.total)
    } catch (error) {
      toast({
        title: 'Error Loading IP Whitelist',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Initial load
  useEffect(() => {
    loadEntries()
  }, [currentPage])

  // Add IP to whitelist
  const handleAdd = async () => {
    if (!newIpAddress.trim()) {
      toast({
        title: 'Validation Error',
        description: 'IP address is required',
        status: 'warning',
        duration: 3000,
      })
      return
    }

    try {
      setIsSubmitting(true)
      await adminApi.addIPToWhitelist({
        ip_address: newIpAddress.trim(),
        description: newDescription.trim() || undefined,
      })

      toast({
        title: 'IP Added to Whitelist',
        description: `${newIpAddress} has been whitelisted successfully`,
        status: 'success',
        duration: 3000,
      })

      setNewIpAddress('')
      setNewDescription('')
      onAddClose()
      loadEntries()
    } catch (error) {
      toast({
        title: 'Error Adding IP',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Update IP whitelist entry
  const handleEdit = async () => {
    if (!editEntry) return

    try {
      setIsSubmitting(true)
      await adminApi.updateIPWhitelistEntry(editEntry.ip_address, {
        description: editDescription.trim() || undefined,
      })

      toast({
        title: 'Whitelist Entry Updated',
        description: `Description for ${editEntry.ip_address} has been updated`,
        status: 'success',
        duration: 3000,
      })

      setEditEntry(null)
      setEditDescription('')
      onEditClose()
      loadEntries()
    } catch (error) {
      toast({
        title: 'Error Updating Entry',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Remove IP from whitelist
  const handleDelete = async () => {
    if (!entryToDelete) return

    try {
      setIsSubmitting(true)
      await adminApi.removeIPFromWhitelist(entryToDelete.ip_address)

      toast({
        title: 'IP Removed from Whitelist',
        description: `${entryToDelete.ip_address} will now be subject to brute force protection`,
        status: 'success',
        duration: 3000,
      })

      setEntryToDelete(null)
      onDeleteClose()
      loadEntries()
    } catch (error) {
      toast({
        title: 'Error Removing IP',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Open edit modal
  const openEditModal = (entry: IPWhitelistEntry) => {
    setEditEntry(entry)
    setEditDescription(entry.description || '')
    onEditOpen()
  }

  // Open delete confirmation
  const openDeleteDialog = (entry: IPWhitelistEntry) => {
    setEntryToDelete(entry)
    onDeleteOpen()
  }

  // Format date
  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleString()
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Flex justify="space-between" align="center">
          <HStack spacing={3}>
            <FiShield size={32} />
            <Heading size="lg">IP Whitelist Management</Heading>
          </HStack>
          <HStack>
            <Tooltip label="Refresh list">
              <IconButton
                aria-label="Refresh"
                icon={<FiRefreshCw />}
                onClick={loadEntries}
                isLoading={isLoading}
              />
            </Tooltip>
            <Button
              leftIcon={<FiPlus />}
              colorScheme="blue"
              onClick={onAddOpen}
            >
              Add IP
            </Button>
          </HStack>
        </Flex>

        {/* Summary */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
          <CardBody>
            <Text fontSize="sm" color="gray.600">
              Total Whitelisted IPs: <strong>{totalEntries}</strong>
            </Text>
            <Text fontSize="sm" color="gray.600" mt={2}>
              Whitelisted IP addresses bypass all brute force protection and rate limiting.
            </Text>
          </CardBody>
        </Card>

        {/* Whitelist Table */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
          <CardBody>
            {isLoading ? (
              <Center p={8}>
                <Spinner size="lg" />
              </Center>
            ) : entries.length === 0 ? (
              <Center p={8}>
                <Text color="gray.500">No whitelisted IP addresses</Text>
              </Center>
            ) : (
              <Table variant="simple" size="sm">
                <Thead>
                  <Tr>
                    <Th>IP Address</Th>
                    <Th>Description</Th>
                    <Th>Added At</Th>
                    <Th>Last Seen</Th>
                    <Th>Access Count</Th>
                    <Th>Actions</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {entries.map((entry) => (
                    <Tr key={entry.ip_address}>
                      <Td>
                        <Badge colorScheme="green" fontSize="sm">
                          {entry.ip_address}
                        </Badge>
                      </Td>
                      <Td>
                        <Text fontSize="sm" color="gray.600">
                          {entry.description || '—'}
                        </Text>
                      </Td>
                      <Td>
                        <Text fontSize="sm">{formatDate(entry.added_at)}</Text>
                      </Td>
                      <Td>
                        <Text fontSize="sm">{formatDate(entry.last_seen)}</Text>
                      </Td>
                      <Td>
                        <Badge>{entry.access_count}</Badge>
                      </Td>
                      <Td>
                        <HStack spacing={2}>
                          <Tooltip label="Edit description">
                            <IconButton
                              aria-label="Edit"
                              icon={<FiEdit2 />}
                              size="sm"
                              onClick={() => openEditModal(entry)}
                            />
                          </Tooltip>
                          <Tooltip label="Remove from whitelist">
                            <IconButton
                              aria-label="Delete"
                              icon={<FiTrash2 />}
                              size="sm"
                              colorScheme="red"
                              onClick={() => openDeleteDialog(entry)}
                            />
                          </Tooltip>
                        </HStack>
                      </Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <Flex justify="space-between" align="center" mt={4}>
                <Text fontSize="sm" color="gray.600">
                  Page {currentPage} of {totalPages}
                </Text>
                <HStack>
                  <IconButton
                    aria-label="First page"
                    icon={<FiChevronsLeft />}
                    size="sm"
                    isDisabled={currentPage === 1}
                    onClick={() => setCurrentPage(1)}
                  />
                  <IconButton
                    aria-label="Previous page"
                    icon={<FiChevronLeft />}
                    size="sm"
                    isDisabled={currentPage === 1}
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  />
                  <IconButton
                    aria-label="Next page"
                    icon={<FiChevronRight />}
                    size="sm"
                    isDisabled={currentPage === totalPages}
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  />
                  <IconButton
                    aria-label="Last page"
                    icon={<FiChevronsRight />}
                    size="sm"
                    isDisabled={currentPage === totalPages}
                    onClick={() => setCurrentPage(totalPages)}
                  />
                </HStack>
              </Flex>
            )}
          </CardBody>
        </Card>
      </VStack>

      {/* Add IP Modal */}
      <Modal isOpen={isAddOpen} onClose={onAddClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Add IP to Whitelist</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>IP Address</FormLabel>
                <Input
                  placeholder="192.168.1.1 or 2001:db8::1"
                  value={newIpAddress}
                  onChange={(e) => setNewIpAddress(e.target.value)}
                />
              </FormControl>
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  placeholder="e.g., Admin office IP, VPN gateway"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  rows={3}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onAddClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={handleAdd}
              isLoading={isSubmitting}
            >
              Add to Whitelist
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Edit Description Modal */}
      <Modal isOpen={isEditOpen} onClose={onEditClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Edit IP Whitelist Entry</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>IP Address</FormLabel>
                <Input
                  value={editEntry?.ip_address || ''}
                  isReadOnly
                  bg="gray.100"
                />
              </FormControl>
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  placeholder="e.g., Admin office IP, VPN gateway"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={3}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onEditClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={handleEdit}
              isLoading={isSubmitting}
            >
              Update
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
              Remove IP from Whitelist
            </AlertDialogHeader>

            <AlertDialogBody>
              Are you sure you want to remove{' '}
              <strong>{entryToDelete?.ip_address}</strong> from the whitelist?
              <br />
              <br />
              This IP will be subject to normal brute force protection after removal.
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Cancel
              </Button>
              <Button
                colorScheme="red"
                onClick={handleDelete}
                ml={3}
                isLoading={isSubmitting}
              >
                Remove
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  )
}
