import { useState, useEffect } from 'react'
import {
  Box,
  Button,
  Heading,
  VStack,
  HStack,
  FormControl,
  FormLabel,
  Input,
  Select,
  Switch,
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
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
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
  FiEdit2,
  FiTrash2,
  FiEye,
  FiUsers,
  FiUserCheck,
  FiUserX,
  FiShield,
  FiChevronsLeft,
  FiChevronLeft,
  FiChevronRight,
  FiChevronsRight,
} from 'react-icons/fi'
import {
  adminApi,
  type User,
  type UserDetail,
  type UserStats,
  type UserUpdateRequest,
} from '../../api/admin'
import { useRef } from 'react'

export const AdminUsersPage = () => {
  // State
  const [users, setUsers] = useState<User[]>([])
  const [stats, setStats] = useState<UserStats | null>(null)
  const [selectedUser, setSelectedUser] = useState<UserDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isUpdating, setIsUpdating] = useState(false)

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(20)
  const [totalPages, setTotalPages] = useState(1)
  const [totalUsers, setTotalUsers] = useState(0)

  // Filters
  const [searchEmail, setSearchEmail] = useState('')
  const [filterActive, setFilterActive] = useState<boolean | undefined>(undefined)
  const [filterAdmin, setFilterAdmin] = useState<boolean | undefined>(undefined)

  // Edit modal
  const { isOpen: isEditOpen, onOpen: onEditOpen, onClose: onEditClose } = useDisclosure()
  const [editFormData, setEditFormData] = useState<UserUpdateRequest>({})

  // Details modal
  const { isOpen: isDetailsOpen, onOpen: onDetailsOpen, onClose: onDetailsClose } = useDisclosure()

  // Delete dialog
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure()
  const [userToDelete, setUserToDelete] = useState<User | null>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)

  const toast = useToast()
  const bgColor = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  // Load users
  const loadUsers = async () => {
    try {
      setIsLoading(true)
      const response = await adminApi.listUsers({
        page: currentPage,
        page_size: pageSize,
        search: searchEmail || undefined,
        is_active: filterActive,
        is_admin: filterAdmin,
      })
      setUsers(response.users)
      setTotalPages(response.total_pages)
      setTotalUsers(response.total)
    } catch (error) {
      toast({
        title: 'Error Loading Users',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Load stats
  const loadStats = async () => {
    try {
      const statsData = await adminApi.getUserStats()
      setStats(statsData)
    } catch (error) {
      console.error('Error loading stats:', error)
    }
  }

  // Initial load
  useEffect(() => {
    loadUsers()
    loadStats()
  }, [currentPage, searchEmail, filterActive, filterAdmin])

  // Handle edit user
  const handleEditUser = (user: User) => {
    setSelectedUser(null)
    setEditFormData({
      is_active: user.is_active,
      is_admin: user.is_admin,
    })
    setSelectedUser(user as any)
    onEditOpen()
  }

  // Handle view details
  const handleViewDetails = async (user: User) => {
    try {
      const details = await adminApi.getUser(user.id)
      setSelectedUser(details)
      onDetailsOpen()
    } catch (error) {
      toast({
        title: 'Error Loading User Details',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    }
  }

  // Handle save edit
  const handleSaveEdit = async () => {
    if (!selectedUser) return

    try {
      setIsUpdating(true)
      await adminApi.updateUser(selectedUser.id, editFormData)
      toast({
        title: 'User Updated',
        description: 'User information updated successfully',
        status: 'success',
        duration: 3000,
      })
      onEditClose()
      loadUsers()
      loadStats()
    } catch (error) {
      toast({
        title: 'Error Updating User',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsUpdating(false)
    }
  }

  // Handle delete user
  const handleDeleteUser = (user: User) => {
    setUserToDelete(user)
    onDeleteOpen()
  }

  const confirmDelete = async () => {
    if (!userToDelete) return

    try {
      await adminApi.deleteUser(userToDelete.id)
      toast({
        title: 'User Deactivated',
        description: 'User has been deactivated successfully',
        status: 'success',
        duration: 3000,
      })
      onDeleteClose()
      loadUsers()
      loadStats()
    } catch (error) {
      toast({
        title: 'Error Deactivating User',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    }
  }

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <Box>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between">
          <Heading size="lg">
            <HStack>
              <FiUsers />
              <Text>User Management</Text>
            </HStack>
          </Heading>
        </HStack>

        {/* Statistics Cards */}
        {stats && (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 5 }} spacing={4}>
            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>
                    <HStack>
                      <FiUsers />
                      <Text>Total Users</Text>
                    </HStack>
                  </StatLabel>
                  <StatNumber>{stats.total_users}</StatNumber>
                  <StatHelpText>All registered users</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>
                    <HStack>
                      <FiUserCheck />
                      <Text>Active Users</Text>
                    </HStack>
                  </StatLabel>
                  <StatNumber color="green.500">{stats.active_users}</StatNumber>
                  <StatHelpText>Currently active</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>
                    <HStack>
                      <FiUserX />
                      <Text>Inactive Users</Text>
                    </HStack>
                  </StatLabel>
                  <StatNumber color="red.500">{stats.inactive_users}</StatNumber>
                  <StatHelpText>Deactivated accounts</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>
                    <HStack>
                      <FiShield />
                      <Text>Admin Users</Text>
                    </HStack>
                  </StatLabel>
                  <StatNumber color="purple.500">{stats.admin_users}</StatNumber>
                  <StatHelpText>With admin privileges</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>New Users (30d)</StatLabel>
                  <StatNumber color="blue.500">{stats.new_users_30d}</StatNumber>
                  <StatHelpText>Last 30 days</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Filters */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
          <CardBody>
            <VStack spacing={4} align="stretch">
              <Heading size="sm">Filters</Heading>
              <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
                <FormControl>
                  <FormLabel>Search by Email</FormLabel>
                  <Input
                    placeholder="Enter email..."
                    value={searchEmail}
                    onChange={(e) => {
                      setSearchEmail(e.target.value)
                      setCurrentPage(1)
                    }}
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Status</FormLabel>
                  <Select
                    value={filterActive === undefined ? 'all' : filterActive.toString()}
                    onChange={(e) => {
                      const value = e.target.value
                      setFilterActive(value === 'all' ? undefined : value === 'true')
                      setCurrentPage(1)
                    }}
                  >
                    <option value="all">All</option>
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel>Role</FormLabel>
                  <Select
                    value={filterAdmin === undefined ? 'all' : filterAdmin.toString()}
                    onChange={(e) => {
                      const value = e.target.value
                      setFilterAdmin(value === 'all' ? undefined : value === 'true')
                      setCurrentPage(1)
                    }}
                  >
                    <option value="all">All</option>
                    <option value="true">Admin</option>
                    <option value="false">Regular</option>
                  </Select>
                </FormControl>
              </SimpleGrid>
            </VStack>
          </CardBody>
        </Card>

        {/* Users Table */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
          <CardBody>
            {isLoading ? (
              <Center py={10}>
                <Spinner size="xl" />
              </Center>
            ) : users.length === 0 ? (
              <Center py={10}>
                <Text color="gray.500">No users found</Text>
              </Center>
            ) : (
              <Box overflowX="auto">
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Email</Th>
                      <Th>Status</Th>
                      <Th>Role</Th>
                      <Th>Created</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {users.map((user) => (
                      <Tr key={user.id}>
                        <Td>
                          <Text fontWeight="medium">{user.email}</Text>
                        </Td>
                        <Td>
                          <Badge colorScheme={user.is_active ? 'green' : 'red'}>
                            {user.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </Td>
                        <Td>
                          <Badge colorScheme={user.is_admin ? 'purple' : 'gray'}>
                            {user.is_admin ? 'Admin' : 'User'}
                          </Badge>
                        </Td>
                        <Td>
                          <Text fontSize="sm" color="text.subtle">
                            {formatDate(user.created_at)}
                          </Text>
                        </Td>
                        <Td>
                          <HStack spacing={2}>
                            <Tooltip label="View Details">
                              <IconButton
                                aria-label="View details"
                                icon={<FiEye />}
                                size="sm"
                                variant="ghost"
                                onClick={() => handleViewDetails(user)}
                              />
                            </Tooltip>
                            <Tooltip label="Edit User">
                              <IconButton
                                aria-label="Edit user"
                                icon={<FiEdit2 />}
                                size="sm"
                                variant="ghost"
                                colorScheme="blue"
                                onClick={() => handleEditUser(user)}
                              />
                            </Tooltip>
                            <Tooltip label="Deactivate User">
                              <IconButton
                                aria-label="Delete user"
                                icon={<FiTrash2 />}
                                size="sm"
                                variant="ghost"
                                colorScheme="red"
                                onClick={() => handleDeleteUser(user)}
                                isDisabled={!user.is_active}
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
                <Text fontSize="sm" color="text.subtle">
                  Showing page {currentPage} of {totalPages} ({totalUsers} total users)
                </Text>
                <HStack spacing={2}>
                  <IconButton
                    aria-label="First page"
                    icon={<FiChevronsLeft />}
                    size="sm"
                    onClick={() => setCurrentPage(1)}
                    isDisabled={currentPage === 1}
                  />
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
                  <IconButton
                    aria-label="Last page"
                    icon={<FiChevronsRight />}
                    size="sm"
                    onClick={() => setCurrentPage(totalPages)}
                    isDisabled={currentPage === totalPages}
                  />
                </HStack>
              </Flex>
            )}
          </CardBody>
        </Card>
      </VStack>

      {/* Edit User Modal */}
      <Modal isOpen={isEditOpen} onClose={onEditClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Edit User</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0" flex="1">
                  Active Status
                </FormLabel>
                <Switch
                  isChecked={editFormData.is_active ?? false}
                  onChange={(e) =>
                    setEditFormData({ ...editFormData, is_active: e.target.checked })
                  }
                />
              </FormControl>

              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0" flex="1">
                  Admin Privileges
                </FormLabel>
                <Switch
                  isChecked={editFormData.is_admin ?? false}
                  onChange={(e) =>
                    setEditFormData({ ...editFormData, is_admin: e.target.checked })
                  }
                />
              </FormControl>

              {selectedUser && (
                <Box w="full" p={3} bg="bg.subtle" borderRadius="md">
                  <Text fontSize="sm" color="text.subtle">
                    <strong>Email:</strong> {selectedUser.email}
                  </Text>
                  <Text fontSize="sm" color="text.subtle">
                    <strong>Created:</strong> {formatDate(selectedUser.created_at)}
                  </Text>
                </Box>
              )}
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onEditClose}>
              Cancel
            </Button>
            <Button colorScheme="blue" onClick={handleSaveEdit} isLoading={isUpdating}>
              Save Changes
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* User Details Modal */}
      <Modal isOpen={isDetailsOpen} onClose={onDetailsClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>User Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedUser && (
              <VStack spacing={4} align="stretch">
                <Box>
                  <Text fontWeight="bold" mb={2}>
                    Email
                  </Text>
                  <Text>{selectedUser.email}</Text>
                </Box>

                <SimpleGrid columns={2} spacing={4}>
                  <Box>
                    <Text fontWeight="bold" mb={2}>
                      Status
                    </Text>
                    <Badge colorScheme={selectedUser.is_active ? 'green' : 'red'}>
                      {selectedUser.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </Box>

                  <Box>
                    <Text fontWeight="bold" mb={2}>
                      Role
                    </Text>
                    <Badge colorScheme={selectedUser.is_admin ? 'purple' : 'gray'}>
                      {selectedUser.is_admin ? 'Admin' : 'User'}
                    </Badge>
                  </Box>
                </SimpleGrid>

                <SimpleGrid columns={2} spacing={4}>
                  <Box>
                    <Text fontWeight="bold" mb={2}>
                      Subscriptions
                    </Text>
                    <Text fontSize="2xl" fontWeight="bold" color="blue.500">
                      {selectedUser.subscription_count}
                    </Text>
                  </Box>

                  <Box>
                    <Text fontWeight="bold" mb={2}>
                      Mailboxes
                    </Text>
                    <Text fontSize="2xl" fontWeight="bold" color="green.500">
                      {selectedUser.mailbox_count}
                    </Text>
                  </Box>
                </SimpleGrid>

                <Box>
                  <Text fontWeight="bold" mb={2}>
                    Created
                  </Text>
                  <Text>{new Date(selectedUser.created_at).toLocaleString()}</Text>
                </Box>

                <Box>
                  <Text fontWeight="bold" mb={2}>
                    Last Updated
                  </Text>
                  <Text>{new Date(selectedUser.updated_at).toLocaleString()}</Text>
                </Box>

                {selectedUser.settings && Object.keys(selectedUser.settings).length > 0 && (
                  <Box>
                    <Text fontWeight="bold" mb={2}>
                      Settings
                    </Text>
                    <Box
                      p={3}
                      bg="bg.subtle"
                      borderRadius="md"
                      fontSize="sm"
                      fontFamily="mono"
                    >
                      <pre>{JSON.stringify(selectedUser.settings, null, 2)}</pre>
                    </Box>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button onClick={onDetailsClose}>Close</Button>
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
              Deactivate User
            </AlertDialogHeader>

            <AlertDialogBody>
              Are you sure you want to deactivate {userToDelete?.email}? This will disable
              their account access but preserve their data.
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Cancel
              </Button>
              <Button colorScheme="red" onClick={confirmDelete} ml={3}>
                Deactivate
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  )
}
