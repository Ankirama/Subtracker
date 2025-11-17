import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Text,
  Input,
  Select,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  IconButton,
  Button,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  useToast,
  useDisclosure,
  InputGroup,
  InputLeftElement,
  Icon,
} from '@chakra-ui/react'
import { FiSearch, FiEdit2, FiTrash2, FiPlus, FiEye, FiRefreshCw, FiDownload } from 'react-icons/fi'
import { subscriptionsAPI } from '../../api/subscriptions'
import { categoriesAPI } from '../../api/categories'
import { Subscription } from '../../types'
import { SubscriptionModal } from './SubscriptionModal'
import { SubscriptionFeedbackModal } from './SubscriptionFeedbackModal'
import { ExportModal } from './ExportModal'

export const SubscriptionsPage = () => {
  const navigate = useNavigate()
  const [searchTerm, setSearchTerm] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState<string>('')
  const [selectedSubscription, setSelectedSubscription] = useState<Subscription | null>(null)
  const [feedbackSubscription, setFeedbackSubscription] = useState<Subscription | null>(null)
  const { isOpen, onOpen, onClose } = useDisclosure()
  const { isOpen: isFeedbackOpen, onOpen: onFeedbackOpen, onClose: onFeedbackClose } = useDisclosure()
  const { isOpen: isExportOpen, onOpen: onExportOpen, onClose: onExportClose } = useDisclosure()

  const queryClient = useQueryClient()
  const toast = useToast()

  const { data, isLoading, error } = useQuery({
    queryKey: ['subscriptions', categoryFilter, activeFilter],
    queryFn: () =>
      subscriptionsAPI.getAll({
        category: categoryFilter || undefined,
        status: activeFilter || undefined,
      }),
  })

  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: categoriesAPI.getAll,
  })

  const deleteMutation = useMutation({
    mutationFn: subscriptionsAPI.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      queryClient.invalidateQueries({ queryKey: ['subscriptionStats'] })
      toast({
        title: 'Subscription deleted',
        status: 'success',
        duration: 3000,
      })
    },
    onError: () => {
      toast({
        title: 'Failed to delete subscription',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const updateStatusMutation = useMutation({
    mutationFn: () => subscriptionsAPI.updateStatus(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      queryClient.invalidateQueries({ queryKey: ['subscriptionStats'] })
      toast({
        title: 'Subscription statuses updated',
        description: `${data.total_activated} activated, ${data.total_deactivated} deactivated`,
        status: 'success',
        duration: 5000,
      })
    },
    onError: () => {
      toast({
        title: 'Failed to update subscription statuses',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const handleEdit = (subscription: Subscription) => {
    setSelectedSubscription(subscription)
    onOpen()
  }

  const handleDelete = async (subscription: Subscription) => {
    // Check if subscription was manually created or AI-detected
    const isManuallyCreated = subscription.extraction_method === 'manual'

    if (isManuallyCreated) {
      // For manually created subscriptions, delete directly
      if (window.confirm('Are you sure you want to delete this subscription?')) {
        deleteMutation.mutate(subscription.id)
      }
    } else {
      // For AI-detected subscriptions, show feedback modal first
      setFeedbackSubscription(subscription)
      onFeedbackOpen()
    }
  }

  const handleFeedbackSubmitted = () => {
    // After feedback is submitted, delete the subscription
    if (feedbackSubscription) {
      deleteMutation.mutate(feedbackSubscription.id)
      setFeedbackSubscription(null)
    }
  }

  const handleNewSubscription = () => {
    setSelectedSubscription(null)
    onOpen()
  }

  const formatCurrency = (amount: number | null | undefined) => {
    if (!amount) return 'N/A'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount)
  }

  const filteredSubscriptions = data?.subscriptions.filter((sub) =>
    sub.provider.toLowerCase().includes(searchTerm.toLowerCase()) ||
    sub.custom_label?.toLowerCase().includes(searchTerm.toLowerCase())
  ) || []

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
          Failed to load subscriptions. Please try again.
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
            <Heading size="lg">Subscriptions</Heading>
            <Text color="gray.600">{data?.total || 0} total subscriptions</Text>
          </Box>
          <HStack spacing={3}>
            <Button
              leftIcon={<Icon as={FiDownload} />}
              colorScheme="purple"
              variant="outline"
              onClick={onExportOpen}
            >
              Export
            </Button>
            <Button
              leftIcon={<Icon as={FiRefreshCw} />}
              colorScheme="green"
              variant="outline"
              onClick={() => updateStatusMutation.mutate()}
              isLoading={updateStatusMutation.isPending}
              loadingText="Updating..."
            >
              Refresh Status
            </Button>
            <Button
              leftIcon={<Icon as={FiPlus} />}
              colorScheme="blue"
              onClick={handleNewSubscription}
            >
              Add Subscription
            </Button>
          </HStack>
        </HStack>

        {/* Filters */}
        <HStack spacing={4}>
          <InputGroup maxW="300px">
            <InputLeftElement>
              <Icon as={FiSearch} color="gray.400" />
            </InputLeftElement>
            <Input
              placeholder="Search subscriptions..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </InputGroup>

          <Select
            maxW="200px"
            placeholder="All categories"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            {categoriesData?.categories.map((category) => (
              <option key={category.name} value={category.name}>
                {category.display_name}
              </option>
            ))}
          </Select>

          <Select
            maxW="150px"
            placeholder="All status"
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value)}
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </Select>
        </HStack>

        {/* Table */}
        <Box overflowX="auto" borderWidth={1} borderRadius="lg">
          <Table variant="simple">
            <Thead bg="gray.50">
              <Tr>
                <Th>Provider</Th>
                <Th>Amount</Th>
                <Th>Billing Cycle</Th>
                <Th>Category</Th>
                <Th>Next Renewal</Th>
                <Th>Status</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {filteredSubscriptions.length === 0 ? (
                <Tr>
                  <Td colSpan={7} textAlign="center" py={8}>
                    <Text color="gray.500">No subscriptions found</Text>
                  </Td>
                </Tr>
              ) : (
                filteredSubscriptions.map((subscription) => (
                  <Tr key={subscription.id} _hover={{ bg: 'gray.50' }}>
                    <Td>
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="bold">{subscription.provider}</Text>
                        {subscription.custom_label && (
                          <Text fontSize="sm" color="gray.600">
                            {subscription.custom_label}
                          </Text>
                        )}
                      </VStack>
                    </Td>
                    <Td fontWeight="medium">
                      {formatCurrency(subscription.amount)}
                    </Td>
                    <Td>
                      <Badge colorScheme="blue" textTransform="capitalize">
                        {subscription.billing_cycle}
                      </Badge>
                    </Td>
                    <Td>
                      <Badge
                        colorScheme={categoriesData?.categories.find(c => c.name === subscription.category)?.color || 'gray'}
                        textTransform="capitalize"
                      >
                        {categoriesData?.categories.find(c => c.name === subscription.category)?.display_name || subscription.category}
                      </Badge>
                    </Td>
                    <Td>
                      {subscription.renewal_date
                        ? new Date(subscription.renewal_date).toLocaleDateString()
                        : 'N/A'}
                    </Td>
                    <Td>
                      <Badge colorScheme={subscription.is_active ? 'green' : 'gray'}>
                        {subscription.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </Td>
                    <Td>
                      <HStack spacing={2}>
                        <IconButton
                          aria-label="View Details"
                          icon={<Icon as={FiEye} />}
                          size="sm"
                          colorScheme="blue"
                          variant="ghost"
                          onClick={() => navigate(`/subscriptions/${subscription.id}`)}
                        />
                        <IconButton
                          aria-label="Edit"
                          icon={<Icon as={FiEdit2} />}
                          size="sm"
                          onClick={() => handleEdit(subscription)}
                        />
                        <IconButton
                          aria-label="Delete"
                          icon={<Icon as={FiTrash2} />}
                          size="sm"
                          colorScheme="red"
                          variant="ghost"
                          onClick={() => handleDelete(subscription)}
                          isLoading={deleteMutation.isPending}
                        />
                      </HStack>
                    </Td>
                  </Tr>
                ))
              )}
            </Tbody>
          </Table>
        </Box>
      </VStack>

      {/* Edit/Create Modal */}
      <SubscriptionModal
        isOpen={isOpen}
        onClose={onClose}
        subscription={selectedSubscription}
      />

      {/* Feedback Modal */}
      {feedbackSubscription && (
        <SubscriptionFeedbackModal
          isOpen={isFeedbackOpen}
          onClose={onFeedbackClose}
          subscription={feedbackSubscription}
          onFeedbackSubmitted={handleFeedbackSubmitted}
        />
      )}

      {/* Export Modal */}
      <ExportModal
        isOpen={isExportOpen}
        onClose={onExportClose}
      />
    </Container>
  )
}
