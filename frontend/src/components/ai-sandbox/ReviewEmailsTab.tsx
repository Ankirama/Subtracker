import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Button,
  ButtonGroup,
  Card,
  CardBody,
  CardHeader,
  Center,
  Checkbox,
  HStack,
  Heading,
  Icon,
  Input,
  InputGroup,
  InputLeftElement,
  Select,
  Spinner,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  VStack,
  useDisclosure,
  useToast,
} from '@chakra-ui/react'
import { FiCheckSquare, FiEye, FiSearch, FiX } from 'react-icons/fi'

import { aiSandboxAPI } from '../../api/aiSandbox'
import type { EmailDetailResponse, UncertainEmail } from '../../types'
import { useUncertainEmailsManagement } from '../../hooks/useUncertainEmailsManagement'
import { CreateSubscriptionModal } from './CreateSubscriptionModal'
import { EmailDetailModal } from './EmailDetailModal'

type FilterType = 'all' | 'low_confidence' | 'extraction_failed'
type SortField = 'date' | 'confidence' | 'status' | 'subject'
type SortOrder = 'asc' | 'desc'

const confidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return 'green'
  if (confidence >= 0.6) return 'yellow'
  return 'red'
}

export const ReviewEmailsTab = () => {
  const toast = useToast()
  const [selectedEmail, setSelectedEmail] = useState<EmailDetailResponse | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterType, setFilterType] = useState<FilterType>('all')
  const [sortField, setSortField] = useState<SortField>('date')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [selectedEmailIds, setSelectedEmailIds] = useState<Set<string>>(new Set())

  const detailModal = useDisclosure()
  const createModal = useDisclosure()

  const { data, isLoading, error } = useQuery({
    queryKey: ['uncertainEmails'],
    queryFn: () => aiSandboxAPI.getUncertainEmails(100),
  })

  const {
    emailDetailMutation,
    createSubscriptionMutation,
    markNotSubscriptionMutation,
    bulkMarkNotSubscriptionMutation,
  } = useUncertainEmailsManagement({
    onEmailDetailLoaded: (email) => {
      setSelectedEmail(email)
      detailModal.onOpen()
    },
    onSubscriptionCreated: () => {
      createModal.onClose()
      detailModal.onClose()
    },
    onMarkedNotSubscription: () => {
      detailModal.onClose()
    },
    onBulkMarked: () => {
      setSelectedEmailIds(new Set())
    },
  })

  const filteredAndSortedEmails = useMemo(() => {
    if (!data?.emails) return []

    let filtered = data.emails

    if (searchTerm) {
      const search = searchTerm.toLowerCase()
      filtered = filtered.filter(
        (email) =>
          email.subject.toLowerCase().includes(search) ||
          email.sender.toLowerCase().includes(search) ||
          email.sender_name?.toLowerCase().includes(search),
      )
    }

    if (filterType === 'low_confidence') {
      filtered = filtered.filter((email) => email.classification_confidence < 0.8)
    } else if (filterType === 'extraction_failed') {
      filtered = filtered.filter((email) => !email.has_linked_subscription)
    }

    return [...filtered].sort((a, b) => {
      let comparison = 0
      switch (sortField) {
        case 'date':
          comparison = new Date(a.date).getTime() - new Date(b.date).getTime()
          break
        case 'confidence':
          comparison = a.classification_confidence - b.classification_confidence
          break
        case 'status':
          comparison =
            (a.has_linked_subscription ? 1 : 0) - (b.has_linked_subscription ? 1 : 0)
          break
        case 'subject':
          comparison = a.subject.localeCompare(b.subject)
          break
      }
      return sortOrder === 'asc' ? comparison : -comparison
    })
  }, [data?.emails, searchTerm, filterType, sortField, sortOrder])

  const filteredStats = useMemo(
    () => ({
      total: filteredAndSortedEmails.length,
      lowConfidence: filteredAndSortedEmails.filter(
        (e) => e.classification_confidence < 0.8,
      ).length,
      extractionFailed: filteredAndSortedEmails.filter((e) => !e.has_linked_subscription)
        .length,
    }),
    [filteredAndSortedEmails],
  )

  const isAllSelected =
    filteredAndSortedEmails.length > 0 &&
    selectedEmailIds.size === filteredAndSortedEmails.length
  const isSomeSelected =
    selectedEmailIds.size > 0 && selectedEmailIds.size < filteredAndSortedEmails.length

  const toggleSelectEmail = (emailId: string, checked: boolean) => {
    const next = new Set(selectedEmailIds)
    if (checked) next.add(emailId)
    else next.delete(emailId)
    setSelectedEmailIds(next)
  }

  const toggleSelectAll = (checked: boolean) => {
    setSelectedEmailIds(
      checked ? new Set(filteredAndSortedEmails.map((email) => email.id)) : new Set(),
    )
  }

  const handleBulkMarkNotSubscription = () => {
    if (selectedEmailIds.size === 0) {
      toast({ title: 'No emails selected', status: 'warning', duration: 3000 })
      return
    }
    bulkMarkNotSubscriptionMutation.mutate({ email_ids: Array.from(selectedEmailIds) })
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
                  <Badge colorScheme="yellow">
                    Low Confidence: {data?.uncertain_classified || 0}
                  </Badge>
                  <Badge colorScheme="red">
                    Extraction Failed: {data?.extraction_failed || 0}
                  </Badge>
                </HStack>
              </HStack>

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
                  <Button
                    size="sm"
                    onClick={() => setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))}
                  >
                    {sortOrder === 'asc' ? '↑' : '↓'}
                  </Button>
                </HStack>
              </HStack>

              {(searchTerm || filterType !== 'all') && (
                <Text fontSize="sm" color="text.subtle">
                  Showing {filteredStats.total} results
                  {searchTerm && ` matching "${searchTerm}"`}
                  {filterType !== 'all' &&
                    ` (${filterType === 'low_confidence' ? 'Low Confidence' : 'Extraction Failed'})`}
                </Text>
              )}

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
                        onChange={(e) => toggleSelectAll(e.target.checked)}
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
                            onChange={(e) => toggleSelectEmail(email.id, e.target.checked)}
                          />
                        </Td>
                        <Td maxW="300px" isTruncated>
                          {email.subject}
                        </Td>
                        <Td>
                          <VStack align="start" spacing={0}>
                            <Text fontSize="sm">{email.sender_name || 'Unknown'}</Text>
                            <Text fontSize="xs" color="gray.500">
                              {email.sender}
                            </Text>
                          </VStack>
                        </Td>
                        <Td>
                          <Text fontSize="sm">
                            {new Date(email.date).toLocaleDateString()}
                          </Text>
                        </Td>
                        <Td>
                          <Badge colorScheme={confidenceColor(email.classification_confidence)}>
                            {(email.classification_confidence * 100).toFixed(0)}%
                          </Badge>
                        </Td>
                        <Td>
                          <Badge
                            colorScheme={email.has_linked_subscription ? 'green' : 'orange'}
                          >
                            {email.has_linked_subscription ? 'Linked' : 'No Subscription'}
                          </Badge>
                        </Td>
                        <Td>
                          <Button
                            size="sm"
                            leftIcon={<FiEye />}
                            onClick={() => emailDetailMutation.mutate(email.id)}
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

      <EmailDetailModal
        email={selectedEmail}
        isOpen={detailModal.isOpen}
        onClose={detailModal.onClose}
        onMarkNotSubscription={() =>
          selectedEmail && markNotSubscriptionMutation.mutate(selectedEmail.id)
        }
        onCreateSubscription={() => selectedEmail && createModal.onOpen()}
        isMarkPending={markNotSubscriptionMutation.isPending}
      />

      <CreateSubscriptionModal
        email={selectedEmail}
        isOpen={createModal.isOpen}
        onClose={createModal.onClose}
        onSubmit={(data) => createSubscriptionMutation.mutate(data)}
        isSubmitting={createSubscriptionMutation.isPending}
      />
    </Box>
  )
}
