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
import { FiSearch, FiEdit2, FiTrash2, FiPlus, FiEye } from 'react-icons/fi'
import { subscriptionsAPI } from '../../api/subscriptions'
import { Subscription } from '../../types'
import { SubscriptionModal } from './SubscriptionModal'

export const SubscriptionsPage = () => {
  const navigate = useNavigate()
  const [searchTerm, setSearchTerm] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState<string>('')
  const [selectedSubscription, setSelectedSubscription] = useState<Subscription | null>(null)
  const { isOpen, onOpen, onClose } = useDisclosure()

  const queryClient = useQueryClient()
  const toast = useToast()

  const { data, isLoading, error } = useQuery({
    queryKey: ['subscriptions', categoryFilter, activeFilter],
    queryFn: () =>
      subscriptionsAPI.getAll({
        category: categoryFilter || undefined,
        is_active: activeFilter ? activeFilter === 'true' : undefined,
      }),
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

  const handleEdit = (subscription: Subscription) => {
    setSelectedSubscription(subscription)
    onOpen()
  }

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this subscription?')) {
      deleteMutation.mutate(id)
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
          <Button
            leftIcon={<Icon as={FiPlus} />}
            colorScheme="blue"
            onClick={handleNewSubscription}
          >
            Add Subscription
          </Button>
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
            <option value="streaming">Streaming</option>
            <option value="software">Software</option>
            <option value="storage">Storage</option>
            <option value="productivity">Productivity</option>
            <option value="entertainment">Entertainment</option>
            <option value="other">Other</option>
          </Select>

          <Select
            maxW="150px"
            placeholder="All status"
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value)}
          >
            <option value="true">Active</option>
            <option value="false">Inactive</option>
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
                      <Badge textTransform="capitalize">
                        {subscription.category}
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
                          onClick={() => handleDelete(subscription.id)}
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
    </Container>
  )
}
