import { useState, useEffect, useRef } from 'react'
import {
  Box,
  Button,
  Heading,
  VStack,
  HStack,
  FormControl,
  FormLabel,
  Select,
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
  FiShield,
  FiAlertTriangle,
  FiCheckCircle,
  FiX,
  FiEye,
  FiTrash2,
  FiChevronsLeft,
  FiChevronLeft,
  FiChevronRight,
  FiChevronsRight,
  FiRefreshCw,
} from 'react-icons/fi'
import {
  adminApi,
  type SecurityEvent,
  type SecurityStats,
} from '../../api/admin'

const SEVERITY_COLORS: Record<string, string> = {
  low: 'blue',
  medium: 'yellow',
  high: 'orange',
  critical: 'red',
}

export const AdminSecurityEventsPage = () => {
  // State
  const [events, setEvents] = useState<SecurityEvent[]>([])
  const [stats, setStats] = useState<SecurityStats | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null)
  const [eventTypes, setEventTypes] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUpdating, setIsUpdating] = useState(false)

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(20)
  const [totalPages, setTotalPages] = useState(1)
  const [totalEvents, setTotalEvents] = useState(0)

  // Filters
  const [filterEventType, setFilterEventType] = useState<string>('')
  const [filterSeverity, setFilterSeverity] = useState<string>('')
  const [filterResolved, setFilterResolved] = useState<boolean | undefined>(undefined)

  // Modals
  const { isOpen: isDetailsOpen, onOpen: onDetailsOpen, onClose: onDetailsClose } = useDisclosure()
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure()
  const [eventToDelete, setEventToDelete] = useState<SecurityEvent | null>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)

  const toast = useToast()
  const bgColor = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  // Load events
  const loadEvents = async () => {
    try {
      setIsLoading(true)
      const response = await adminApi.listSecurityEvents({
        page: currentPage,
        page_size: pageSize,
        event_type: filterEventType || undefined,
        severity: filterSeverity || undefined,
        is_resolved: filterResolved,
      })
      setEvents(response.items)
      setTotalPages(response.total_pages)
      setTotalEvents(response.total)
    } catch (error) {
      toast({
        title: 'Error Loading Security Events',
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
      const statsData = await adminApi.getSecurityStats()
      setStats(statsData)
    } catch (error) {
      console.error('Error loading stats:', error)
    }
  }

  // Load event types
  const loadEventTypes = async () => {
    try {
      const typesData = await adminApi.getEventTypes()
      setEventTypes(typesData.event_types)
    } catch (error) {
      console.error('Error loading event types:', error)
    }
  }

  // Initial load
  useEffect(() => {
    loadEvents()
    loadStats()
    loadEventTypes()
  }, [currentPage, filterEventType, filterSeverity, filterResolved])

  // Handle view details
  const handleViewDetails = (event: SecurityEvent) => {
    setSelectedEvent(event)
    onDetailsOpen()
  }

  // Handle toggle resolved
  const handleToggleResolved = async (event: SecurityEvent) => {
    try {
      setIsUpdating(true)
      await adminApi.updateSecurityEvent(event.id, {
        is_resolved: !event.is_resolved,
      })
      toast({
        title: event.is_resolved ? 'Event Marked as Unresolved' : 'Event Marked as Resolved',
        status: 'success',
        duration: 3000,
      })
      loadEvents()
      loadStats()
    } catch (error) {
      toast({
        title: 'Error Updating Event',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsUpdating(false)
    }
  }

  // Handle delete
  const handleDeleteEvent = (event: SecurityEvent) => {
    setEventToDelete(event)
    onDeleteOpen()
  }

  const confirmDelete = async () => {
    if (!eventToDelete) return

    try {
      await adminApi.deleteSecurityEvent(eventToDelete.id)
      toast({
        title: 'Event Deleted',
        description: 'Security event has been deleted successfully',
        status: 'success',
        duration: 3000,
      })
      onDeleteClose()
      loadEvents()
      loadStats()
    } catch (error) {
      toast({
        title: 'Error Deleting Event',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    }
  }

  // Handle refresh
  const handleRefresh = () => {
    setCurrentPage(1)
    loadEvents()
    loadStats()
  }

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <Box>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between">
          <Heading size="lg">
            <HStack>
              <FiShield />
              <Text>Security Events</Text>
            </HStack>
          </Heading>
          <Tooltip label="Refresh Events">
            <IconButton
              aria-label="Refresh events"
              icon={<FiRefreshCw />}
              onClick={handleRefresh}
              colorScheme="blue"
              variant="outline"
            />
          </Tooltip>
        </HStack>

        {/* Statistics Cards */}
        {stats && (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 5 }} spacing={4}>
            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>Total Events</StatLabel>
                  <StatNumber>{stats.total_events}</StatNumber>
                  <StatHelpText>All time</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>
                    <HStack>
                      <FiAlertTriangle />
                      <Text>Unresolved</Text>
                    </HStack>
                  </StatLabel>
                  <StatNumber color="orange.500">{stats.unresolved_events}</StatNumber>
                  <StatHelpText>Requiring attention</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>Events (24h)</StatLabel>
                  <StatNumber color="blue.500">{stats.events_24h}</StatNumber>
                  <StatHelpText>Last 24 hours</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>
                    <HStack>
                      <FiX />
                      <Text>Critical</Text>
                    </HStack>
                  </StatLabel>
                  <StatNumber color="red.500">{stats.critical_unresolved}</StatNumber>
                  <StatHelpText>Unresolved critical</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <VStack align="start" spacing={1}>
                  <Text fontSize="sm" fontWeight="bold">
                    By Severity (Unresolved)
                  </Text>
                  <HStack spacing={3}>
                    <Badge colorScheme="red" fontSize="xs">
                      C: {stats.by_severity.critical}
                    </Badge>
                    <Badge colorScheme="orange" fontSize="xs">
                      H: {stats.by_severity.high}
                    </Badge>
                    <Badge colorScheme="yellow" fontSize="xs">
                      M: {stats.by_severity.medium}
                    </Badge>
                    <Badge colorScheme="blue" fontSize="xs">
                      L: {stats.by_severity.low}
                    </Badge>
                  </HStack>
                </VStack>
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
                  <FormLabel>Event Type</FormLabel>
                  <Select
                    value={filterEventType}
                    onChange={(e) => {
                      setFilterEventType(e.target.value)
                      setCurrentPage(1)
                    }}
                  >
                    <option value="">All Types</option>
                    {eventTypes.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel>Severity</FormLabel>
                  <Select
                    value={filterSeverity}
                    onChange={(e) => {
                      setFilterSeverity(e.target.value)
                      setCurrentPage(1)
                    }}
                  >
                    <option value="">All Levels</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel>Status</FormLabel>
                  <Select
                    value={
                      filterResolved === undefined ? 'all' : filterResolved.toString()
                    }
                    onChange={(e) => {
                      const value = e.target.value
                      setFilterResolved(
                        value === 'all' ? undefined : value === 'true'
                      )
                      setCurrentPage(1)
                    }}
                  >
                    <option value="all">All</option>
                    <option value="false">Unresolved</option>
                    <option value="true">Resolved</option>
                  </Select>
                </FormControl>
              </SimpleGrid>
            </VStack>
          </CardBody>
        </Card>

        {/* Events Table */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
          <CardBody>
            {isLoading ? (
              <Center py={10}>
                <Spinner size="xl" />
              </Center>
            ) : events.length === 0 ? (
              <Center py={10}>
                <Text color="gray.500">No security events found</Text>
              </Center>
            ) : (
              <Box overflowX="auto">
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Time</Th>
                      <Th>Event Type</Th>
                      <Th>Severity</Th>
                      <Th>IP Address</Th>
                      <Th>Status</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {events.map((event) => (
                      <Tr key={event.id}>
                        <Td>
                          <Text fontSize="sm">{formatDate(event.created_at)}</Text>
                        </Td>
                        <Td>
                          <Text fontWeight="medium">{event.event_type}</Text>
                        </Td>
                        <Td>
                          {event.severity && (
                            <Badge colorScheme={SEVERITY_COLORS[event.severity]}>
                              {event.severity.toUpperCase()}
                            </Badge>
                          )}
                        </Td>
                        <Td>
                          <Text fontSize="sm" fontFamily="mono">
                            {event.ip_address || '-'}
                          </Text>
                        </Td>
                        <Td>
                          <Badge
                            colorScheme={event.is_resolved ? 'green' : 'orange'}
                          >
                            {event.is_resolved ? 'Resolved' : 'Unresolved'}
                          </Badge>
                        </Td>
                        <Td>
                          <HStack spacing={2}>
                            <Tooltip label="View Details">
                              <IconButton
                                aria-label="View details"
                                icon={<FiEye />}
                                size="sm"
                                variant="ghost"
                                onClick={() => handleViewDetails(event)}
                              />
                            </Tooltip>
                            <Tooltip
                              label={
                                event.is_resolved
                                  ? 'Mark as Unresolved'
                                  : 'Mark as Resolved'
                              }
                            >
                              <IconButton
                                aria-label="Toggle resolved"
                                icon={
                                  event.is_resolved ? <FiX /> : <FiCheckCircle />
                                }
                                size="sm"
                                variant="ghost"
                                colorScheme={event.is_resolved ? 'orange' : 'green'}
                                onClick={() => handleToggleResolved(event)}
                                isLoading={isUpdating}
                              />
                            </Tooltip>
                            <Tooltip label="Delete Event">
                              <IconButton
                                aria-label="Delete event"
                                icon={<FiTrash2 />}
                                size="sm"
                                variant="ghost"
                                colorScheme="red"
                                onClick={() => handleDeleteEvent(event)}
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
                  Showing page {currentPage} of {totalPages} ({totalEvents} total
                  events)
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
                    onClick={() =>
                      setCurrentPage((p) => Math.min(totalPages, p + 1))
                    }
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

      {/* Event Details Modal */}
      <Modal isOpen={isDetailsOpen} onClose={onDetailsClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Security Event Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedEvent && (
              <VStack spacing={4} align="stretch">
                <Box>
                  <Text fontWeight="bold" mb={2}>
                    Event Type
                  </Text>
                  <Text>{selectedEvent.event_type}</Text>
                </Box>

                <SimpleGrid columns={2} spacing={4}>
                  <Box>
                    <Text fontWeight="bold" mb={2}>
                      Severity
                    </Text>
                    {selectedEvent.severity && (
                      <Badge
                        colorScheme={SEVERITY_COLORS[selectedEvent.severity]}
                        fontSize="md"
                      >
                        {selectedEvent.severity.toUpperCase()}
                      </Badge>
                    )}
                  </Box>

                  <Box>
                    <Text fontWeight="bold" mb={2}>
                      Status
                    </Text>
                    <Badge
                      colorScheme={selectedEvent.is_resolved ? 'green' : 'orange'}
                      fontSize="md"
                    >
                      {selectedEvent.is_resolved ? 'Resolved' : 'Unresolved'}
                    </Badge>
                  </Box>
                </SimpleGrid>

                <Box>
                  <Text fontWeight="bold" mb={2}>
                    IP Address
                  </Text>
                  <Text fontFamily="mono">
                    {selectedEvent.ip_address || 'Not recorded'}
                  </Text>
                </Box>

                {selectedEvent.user_agent && (
                  <Box>
                    <Text fontWeight="bold" mb={2}>
                      User Agent
                    </Text>
                    <Text fontSize="sm">{selectedEvent.user_agent}</Text>
                  </Box>
                )}

                <Box>
                  <Text fontWeight="bold" mb={2}>
                    Created At
                  </Text>
                  <Text>{formatDate(selectedEvent.created_at)}</Text>
                </Box>

                {selectedEvent.resolved_at && (
                  <Box>
                    <Text fontWeight="bold" mb={2}>
                      Resolved At
                    </Text>
                    <Text>{formatDate(selectedEvent.resolved_at)}</Text>
                  </Box>
                )}

                {selectedEvent.details &&
                  Object.keys(selectedEvent.details).length > 0 && (
                    <Box>
                      <Text fontWeight="bold" mb={2}>
                        Details
                      </Text>
                      <Box
                        p={3}
                        bg="bg.subtle"
                        borderRadius="md"
                        fontSize="sm"
                        fontFamily="mono"
                      >
                        <pre>{JSON.stringify(selectedEvent.details, null, 2)}</pre>
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
              Delete Security Event
            </AlertDialogHeader>

            <AlertDialogBody>
              Are you sure you want to delete this security event? This action
              cannot be undone.
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
