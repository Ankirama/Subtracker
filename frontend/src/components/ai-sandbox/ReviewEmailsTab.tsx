import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  VStack,
  HStack,
  Text,
  Badge,
  Button,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Alert,
  AlertIcon,
  Spinner,
  Center,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  ModalFooter,
  useDisclosure,
  FormControl,
  FormLabel,
  Input,
  Select,
  Textarea,
  useToast,
  Divider,
  Code,
  InputGroup,
  InputLeftElement,
  Icon,
  ButtonGroup,
  Checkbox,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
} from '@chakra-ui/react'
import { FiEye, FiPlus, FiSearch, FiX, FiCheckSquare } from 'react-icons/fi'
import DOMPurify from 'dompurify'
import { aiSandboxAPI } from '../../api/aiSandbox'
import { UncertainEmail, EmailDetailResponse } from '../../types'

type FilterType = 'all' | 'low_confidence' | 'extraction_failed'
type SortField = 'date' | 'confidence' | 'status' | 'subject'
type SortOrder = 'asc' | 'desc'

export const ReviewEmailsTab = () => {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [selectedEmail, setSelectedEmail] = useState<EmailDetailResponse | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterType, setFilterType] = useState<FilterType>('all')
  const [sortField, setSortField] = useState<SortField>('date')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [selectedEmailIds, setSelectedEmailIds] = useState<Set<string>>(new Set())

  const { isOpen: isDetailOpen, onOpen: onDetailOpen, onClose: onDetailClose } = useDisclosure()
  const { isOpen: isCreateOpen, onOpen: onCreateOpen, onClose: onCreateClose } = useDisclosure()

  const [subscriptionData, setSubscriptionData] = useState({
    provider: '',
    amount: '',
    currency: 'EUR',
    billing_cycle: 'monthly',
    renewal_date: '',
    custom_label: '',
    category: 'other',
    notes: '',
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['uncertainEmails'],
    queryFn: () => aiSandboxAPI.getUncertainEmails(100),
  })

  // Filter and sort emails
  const filteredAndSortedEmails = useMemo(() => {
    if (!data?.emails) return []

    let filtered = data.emails

    // Apply search filter
    if (searchTerm) {
      const search = searchTerm.toLowerCase()
      filtered = filtered.filter(
        (email) =>
          email.subject.toLowerCase().includes(search) ||
          email.sender.toLowerCase().includes(search) ||
          email.sender_name?.toLowerCase().includes(search)
      )
    }

    // Apply type filter
    if (filterType === 'low_confidence') {
      filtered = filtered.filter((email) => email.classification_confidence < 0.8)
    } else if (filterType === 'extraction_failed') {
      filtered = filtered.filter((email) => !email.has_linked_subscription)
    }

    // Apply sorting
    const sorted = [...filtered].sort((a, b) => {
      let comparison = 0

      switch (sortField) {
        case 'date':
          comparison = new Date(a.date).getTime() - new Date(b.date).getTime()
          break
        case 'confidence':
          comparison = a.classification_confidence - b.classification_confidence
          break
        case 'status':
          comparison = (a.has_linked_subscription ? 1 : 0) - (b.has_linked_subscription ? 1 : 0)
          break
        case 'subject':
          comparison = a.subject.localeCompare(b.subject)
          break
      }

      return sortOrder === 'asc' ? comparison : -comparison
    })

    return sorted
  }, [data?.emails, searchTerm, filterType, sortField, sortOrder])

  // Calculate filtered statistics
  const filteredStats = useMemo(() => {
    if (!filteredAndSortedEmails) return { total: 0, lowConfidence: 0, extractionFailed: 0 }

    return {
      total: filteredAndSortedEmails.length,
      lowConfidence: filteredAndSortedEmails.filter((e) => e.classification_confidence < 0.8).length,
      extractionFailed: filteredAndSortedEmails.filter((e) => !e.has_linked_subscription).length,
    }
  }, [filteredAndSortedEmails])

  const emailDetailMutation = useMutation({
    mutationFn: aiSandboxAPI.getEmailDetail,
    onSuccess: (data) => {
      setSelectedEmail(data)
      onDetailOpen()
    },
    onError: () => {
      toast({
        title: 'Failed to load email details',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const createSubscriptionMutation = useMutation({
    mutationFn: aiSandboxAPI.createSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uncertainEmails'] })
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      onCreateClose()
      onDetailClose()
      toast({
        title: 'Subscription created successfully',
        status: 'success',
        duration: 3000,
      })
      setSubscriptionData({
        provider: '',
        amount: '',
        currency: 'EUR',
        billing_cycle: 'monthly',
        renewal_date: '',
        custom_label: '',
        category: 'other',
        notes: '',
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to create subscription',
        description: error.response?.data?.detail || 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const markNotSubscriptionMutation = useMutation({
    mutationFn: aiSandboxAPI.markNotSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uncertainEmails'] })
      onDetailClose()
      toast({
        title: 'Email marked as not a subscription',
        description: 'This email will be removed from uncertain emails list',
        status: 'success',
        duration: 3000,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to mark email',
        description: error.response?.data?.detail || 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const bulkMarkNotSubscriptionMutation = useMutation({
    mutationFn: aiSandboxAPI.bulkMarkNotSubscription,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['uncertainEmails'] })
      setSelectedEmailIds(new Set())
      toast({
        title: 'Bulk operation completed',
        description: `${result.processed} emails marked as not subscriptions${result.failed > 0 ? `, ${result.failed} failed` : ''}`,
        status: result.failed > 0 ? 'warning' : 'success',
        duration: 5000,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Bulk operation failed',
        description: error.response?.data?.detail || 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    },
  })

  const handleViewEmail = (emailId: string) => {
    emailDetailMutation.mutate(emailId)
  }

  const handleCreateSubscription = () => {
    if (!selectedEmail || !subscriptionData.provider) {
      toast({
        title: 'Provider is required',
        status: 'warning',
        duration: 3000,
      })
      return
    }

    // Convert date string to ISO datetime format
    let renewalDateTime = null
    if (subscriptionData.renewal_date) {
      renewalDateTime = new Date(subscriptionData.renewal_date + 'T00:00:00').toISOString()
    }

    createSubscriptionMutation.mutate({
      email_id: selectedEmail.id,
      provider: subscriptionData.provider,
      amount: subscriptionData.amount ? parseFloat(subscriptionData.amount) : null,
      currency: subscriptionData.currency || null,
      billing_cycle: subscriptionData.billing_cycle || null,
      renewal_date: renewalDateTime,
      custom_label: subscriptionData.custom_label || null,
      category: subscriptionData.category || 'other',
      notes: subscriptionData.notes || null,
    })
  }

  const openCreateModal = () => {
    if (selectedEmail) {
      setSubscriptionData({
        provider: '',
        amount: '',
        currency: 'EUR',
        billing_cycle: 'monthly',
        renewal_date: '',
        custom_label: '',
        category: 'other',
        notes: '',
      })
      onCreateOpen()
    }
  }

  const handleMarkNotSubscription = () => {
    if (selectedEmail) {
      markNotSubscriptionMutation.mutate(selectedEmail.id)
    }
  }

  const handleBulkMarkNotSubscription = () => {
    if (selectedEmailIds.size === 0) {
      toast({
        title: 'No emails selected',
        status: 'warning',
        duration: 3000,
      })
      return
    }

    bulkMarkNotSubscriptionMutation.mutate({
      email_ids: Array.from(selectedEmailIds),
    })
  }

  const handleSelectEmail = (emailId: string, checked: boolean) => {
    const newSelected = new Set(selectedEmailIds)
    if (checked) {
      newSelected.add(emailId)
    } else {
      newSelected.delete(emailId)
    }
    setSelectedEmailIds(newSelected)
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const allIds = new Set(filteredAndSortedEmails.map((email) => email.id))
      setSelectedEmailIds(allIds)
    } else {
      setSelectedEmailIds(new Set())
    }
  }

  const isAllSelected = filteredAndSortedEmails.length > 0 && selectedEmailIds.size === filteredAndSortedEmails.length
  const isSomeSelected = selectedEmailIds.size > 0 && selectedEmailIds.size < filteredAndSortedEmails.length

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'green'
    if (confidence >= 0.6) return 'yellow'
    return 'red'
  }

  const toggleSortOrder = () => {
    setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
  }

  if (isLoading) {
    return (
      <Center py={10}>
        <Spinner size="xl" />
      </Center>
    )
  }

  if (error) {
    return (
      <Alert status="error">
        <AlertIcon />
        Failed to load uncertain emails
      </Alert>
    )
  }

  return (
    <Box>
      <Alert status="info" mb={6}>
        <AlertIcon />
        Review emails with low confidence classification or failed extraction. You can manually create subscriptions from these emails.
      </Alert>

      {data && data.emails.length === 0 ? (
        <Alert status="success">
          <AlertIcon />
          No uncertain emails found! All emails have been classified with high confidence.
        </Alert>
      ) : (
        <Card>
          <CardHeader>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Heading size="md">Uncertain Emails ({data?.total || 0})</Heading>
                <HStack spacing={4}>
                  <Badge colorScheme="yellow">Low Confidence: {data?.uncertain_classified || 0}</Badge>
                  <Badge colorScheme="red">Extraction Failed: {data?.extraction_failed || 0}</Badge>
                </HStack>
              </HStack>

              {/* Search and Filters */}
              <HStack spacing={4} wrap="wrap">
                <InputGroup maxW="400px">
                  <InputLeftElement>
                    <Icon as={FiSearch} color="gray.400" />
                  </InputLeftElement>
                  <Input
                    placeholder="Search by subject or sender..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </InputGroup>

                <ButtonGroup size="sm" isAttached variant="outline">
                  <Button
                    colorScheme={filterType === 'all' ? 'blue' : 'gray'}
                    onClick={() => setFilterType('all')}
                  >
                    All ({data?.total || 0})
                  </Button>
                  <Button
                    colorScheme={filterType === 'low_confidence' ? 'blue' : 'gray'}
                    onClick={() => setFilterType('low_confidence')}
                  >
                    Low Confidence ({data?.uncertain_classified || 0})
                  </Button>
                  <Button
                    colorScheme={filterType === 'extraction_failed' ? 'blue' : 'gray'}
                    onClick={() => setFilterType('extraction_failed')}
                  >
                    Extraction Failed ({data?.extraction_failed || 0})
                  </Button>
                </ButtonGroup>

                <HStack>
                  <Text fontSize="sm" fontWeight="medium">Sort by:</Text>
                  <Select
                    size="sm"
                    value={sortField}
                    onChange={(e) => setSortField(e.target.value as SortField)}
                    w="150px"
                  >
                    <option value="date">Date</option>
                    <option value="confidence">Confidence</option>
                    <option value="status">Status</option>
                    <option value="subject">Subject</option>
                  </Select>
                  <Button size="sm" onClick={toggleSortOrder}>
                    {sortOrder === 'asc' ? '↑' : '↓'}
                  </Button>
                </HStack>
              </HStack>

              {/* Filtered Results Info */}
              {(searchTerm || filterType !== 'all') && (
                <Text fontSize="sm" color="gray.600">
                  Showing {filteredStats.total} results
                  {searchTerm && ` matching "${searchTerm}"`}
                  {filterType !== 'all' && ` (${filterType === 'low_confidence' ? 'Low Confidence' : 'Extraction Failed'})`}
                </Text>
              )}

              {/* Bulk Action Bar */}
              {selectedEmailIds.size > 0 && (
                <Alert status="info" variant="left-accent">
                  <HStack flex={1} justify="space-between">
                    <HStack>
                      <Icon as={FiCheckSquare} />
                      <Text fontWeight="medium">
                        {selectedEmailIds.size} email{selectedEmailIds.size > 1 ? 's' : ''} selected
                      </Text>
                    </HStack>
                    <ButtonGroup size="sm">
                      <Button
                        colorScheme="red"
                        variant="outline"
                        leftIcon={<FiX />}
                        onClick={handleBulkMarkNotSubscription}
                        isLoading={bulkMarkNotSubscriptionMutation.isPending}
                      >
                        Mark as Not Subscription
                      </Button>
                      <Button variant="ghost" onClick={() => setSelectedEmailIds(new Set())}>
                        Clear Selection
                      </Button>
                    </ButtonGroup>
                  </HStack>
                </Alert>
              )}
            </VStack>
          </CardHeader>
          <CardBody>
            <Box overflowX="auto">
              <Table variant="simple">
                <Thead>
                  <Tr>
                    <Th width="40px">
                      <Checkbox
                        isChecked={isAllSelected}
                        isIndeterminate={isSomeSelected}
                        onChange={(e) => handleSelectAll(e.target.checked)}
                      />
                    </Th>
                    <Th>Subject</Th>
                    <Th>Sender</Th>
                    <Th>Date</Th>
                    <Th>Confidence</Th>
                    <Th>Status</Th>
                    <Th>Actions</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {filteredAndSortedEmails.length === 0 ? (
                    <Tr>
                      <Td colSpan={7} textAlign="center" py={8}>
                        <Text color="gray.500">No emails match your filters</Text>
                      </Td>
                    </Tr>
                  ) : (
                    filteredAndSortedEmails.map((email: UncertainEmail) => (
                      <Tr key={email.id}>
                        <Td>
                          <Checkbox
                            isChecked={selectedEmailIds.has(email.id)}
                            onChange={(e) => handleSelectEmail(email.id, e.target.checked)}
                          />
                        </Td>
                        <Td maxW="300px" isTruncated>
                          {email.subject}
                        </Td>
                        <Td>
                          <VStack align="start" spacing={0}>
                            <Text fontSize="sm">{email.sender_name || 'Unknown'}</Text>
                            <Text fontSize="xs" color="gray.500">{email.sender}</Text>
                          </VStack>
                        </Td>
                        <Td>
                          <Text fontSize="sm">{new Date(email.date).toLocaleDateString()}</Text>
                        </Td>
                        <Td>
                          <Badge colorScheme={getConfidenceColor(email.classification_confidence)}>
                            {(email.classification_confidence * 100).toFixed(0)}%
                          </Badge>
                        </Td>
                        <Td>
                          <Badge colorScheme={email.has_linked_subscription ? 'green' : 'orange'}>
                            {email.has_linked_subscription ? 'Linked' : 'No Subscription'}
                          </Badge>
                        </Td>
                        <Td>
                          <Button
                            size="sm"
                            leftIcon={<FiEye />}
                            onClick={() => handleViewEmail(email.id)}
                            isLoading={emailDetailMutation.isPending}
                          >
                            Review
                          </Button>
                        </Td>
                      </Tr>
                    ))
                  )}
                </Tbody>
              </Table>
            </Box>
          </CardBody>
        </Card>
      )}

      {/* Email Detail Modal */}
      <Modal isOpen={isDetailOpen} onClose={onDetailClose} size="4xl" scrollBehavior="inside">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Email Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedEmail && (
              <VStack spacing={4} align="stretch">
                <Box>
                  <Text fontWeight="bold" mb={2}>Subject:</Text>
                  <Text>{selectedEmail.subject}</Text>
                </Box>

                <HStack spacing={4}>
                  <Box flex={1}>
                    <Text fontWeight="bold" mb={2}>From:</Text>
                    <Text>{selectedEmail.sender_name || 'Unknown'}</Text>
                    <Text fontSize="sm" color="gray.500">{selectedEmail.sender}</Text>
                  </Box>
                  <Box flex={1}>
                    <Text fontWeight="bold" mb={2}>To:</Text>
                    <Text fontSize="sm">{selectedEmail.recipient}</Text>
                  </Box>
                </HStack>

                <HStack spacing={4}>
                  <Box>
                    <Text fontWeight="bold" mb={2}>Date:</Text>
                    <Text>{new Date(selectedEmail.date).toLocaleString()}</Text>
                  </Box>
                  <Box>
                    <Text fontWeight="bold" mb={2}>Confidence:</Text>
                    <Badge colorScheme={getConfidenceColor(selectedEmail.classification_confidence)}>
                      {(selectedEmail.classification_confidence * 100).toFixed(0)}%
                    </Badge>
                  </Box>
                  <Box>
                    <Text fontWeight="bold" mb={2}>Subscription Status:</Text>
                    <Badge colorScheme={selectedEmail.has_linked_subscription ? 'green' : 'orange'}>
                      {selectedEmail.has_linked_subscription ? 'Linked' : 'No Subscription'}
                    </Badge>
                  </Box>
                </HStack>

                <Divider />

                <Box>
                  <Text fontWeight="bold" mb={2}>Email Body:</Text>
                  <Tabs colorScheme="blue" variant="enclosed">
                    <TabList>
                      <Tab>Source Code</Tab>
                      {selectedEmail.body_html && <Tab>Rendered HTML</Tab>}
                    </TabList>
                    <TabPanels>
                      <TabPanel p={0} pt={4}>
                        <Box bg="gray.50" p={4} borderRadius="md" maxH="400px" overflowY="auto">
                          <Text whiteSpace="pre-wrap" fontFamily="monospace" fontSize="sm">
                            {selectedEmail.body_html || selectedEmail.body_text || 'No content'}
                          </Text>
                        </Box>
                      </TabPanel>
                      {selectedEmail.body_html && (
                        <TabPanel p={0} pt={4}>
                          <Box
                            bg="white"
                            p={4}
                            borderRadius="md"
                            border="1px solid"
                            borderColor="gray.200"
                            maxH="400px"
                            overflowY="auto"
                            dangerouslySetInnerHTML={{
                              __html: DOMPurify.sanitize(selectedEmail.body_html),
                            }}
                          />
                        </TabPanel>
                      )}
                    </TabPanels>
                  </Tabs>
                </Box>

                {selectedEmail.classification_reasoning && (
                  <Box>
                    <Text fontWeight="bold" mb={2}>Classification Reasoning:</Text>
                    <Box bg="gray.50" p={4} borderRadius="md" maxH="200px" overflowY="auto">
                      <Code display="block" whiteSpace="pre-wrap" fontSize="xs">
                        {JSON.stringify(selectedEmail.classification_reasoning, null, 2)}
                      </Code>
                    </Box>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <HStack spacing={3} flex={1} justify="space-between">
              <Box>
                {selectedEmail && selectedEmail.is_subscription && (
                  <Button
                    colorScheme="red"
                    variant="outline"
                    leftIcon={<FiX />}
                    onClick={handleMarkNotSubscription}
                    isLoading={markNotSubscriptionMutation.isPending}
                  >
                    Not a Subscription
                  </Button>
                )}
              </Box>
              <HStack spacing={3}>
                {selectedEmail && !selectedEmail.has_linked_subscription && (
                  <Button colorScheme="green" leftIcon={<FiPlus />} onClick={openCreateModal}>
                    Create Subscription
                  </Button>
                )}
                <Button variant="ghost" onClick={onDetailClose}>
                  Close
                </Button>
              </HStack>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Create Subscription Modal */}
      <Modal isOpen={isCreateOpen} onClose={onCreateClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create Subscription Manually</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Provider</FormLabel>
                <Input
                  placeholder="Service name (e.g., Netflix, Spotify)"
                  value={subscriptionData.provider}
                  onChange={(e) => setSubscriptionData({ ...subscriptionData, provider: e.target.value })}
                />
              </FormControl>

              <HStack w="full" spacing={4}>
                <FormControl flex={2}>
                  <FormLabel>Amount</FormLabel>
                  <Input
                    type="number"
                    step="0.01"
                    placeholder="9.99"
                    value={subscriptionData.amount}
                    onChange={(e) => setSubscriptionData({ ...subscriptionData, amount: e.target.value })}
                  />
                </FormControl>

                <FormControl flex={1}>
                  <FormLabel>Currency</FormLabel>
                  <Select
                    value={subscriptionData.currency}
                    onChange={(e) => setSubscriptionData({ ...subscriptionData, currency: e.target.value })}
                  >
                    <option value="EUR">EUR</option>
                    <option value="USD">USD</option>
                    <option value="GBP">GBP</option>
                  </Select>
                </FormControl>
              </HStack>

              <FormControl>
                <FormLabel>Billing Cycle</FormLabel>
                <Select
                  value={subscriptionData.billing_cycle}
                  onChange={(e) => setSubscriptionData({ ...subscriptionData, billing_cycle: e.target.value })}
                >
                  <option value="monthly">Monthly</option>
                  <option value="yearly">Yearly</option>
                  <option value="weekly">Weekly</option>
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Renewal Date</FormLabel>
                <Input
                  type="date"
                  value={subscriptionData.renewal_date}
                  onChange={(e) => setSubscriptionData({ ...subscriptionData, renewal_date: e.target.value })}
                />
              </FormControl>

              <FormControl>
                <FormLabel>Custom Label</FormLabel>
                <Input
                  placeholder="e.g., Family Plan, Premium Tier"
                  value={subscriptionData.custom_label}
                  onChange={(e) => setSubscriptionData({ ...subscriptionData, custom_label: e.target.value })}
                />
              </FormControl>

              <FormControl>
                <FormLabel>Category</FormLabel>
                <Select
                  value={subscriptionData.category}
                  onChange={(e) => setSubscriptionData({ ...subscriptionData, category: e.target.value })}
                >
                  <option value="streaming">Streaming</option>
                  <option value="software">Software</option>
                  <option value="storage">Storage</option>
                  <option value="productivity">Productivity</option>
                  <option value="entertainment">Entertainment</option>
                  <option value="fitness">Fitness</option>
                  <option value="gaming">Gaming</option>
                  <option value="news">News</option>
                  <option value="education">Education</option>
                  <option value="music">Music</option>
                  <option value="other">Other</option>
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Notes</FormLabel>
                <Textarea
                  placeholder="Additional notes..."
                  value={subscriptionData.notes}
                  onChange={(e) => setSubscriptionData({ ...subscriptionData, notes: e.target.value })}
                  rows={3}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button
              colorScheme="blue"
              onClick={handleCreateSubscription}
              isLoading={createSubscriptionMutation.isPending}
              mr={3}
            >
              Create Subscription
            </Button>
            <Button variant="ghost" onClick={onCreateClose}>
              Cancel
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  )
}
