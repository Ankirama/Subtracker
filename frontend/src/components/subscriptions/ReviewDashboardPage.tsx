import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Container,
  Heading,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Card,
  CardBody,
  VStack,
  HStack,
  Text,
  Badge,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  Icon,
  Select,
  Button,
  Divider,
  useColorMode,
} from '@chakra-ui/react'
import {
  FiAlertTriangle,
  FiAlertCircle,
  FiInfo,
  FiCheckCircle,
  FiRefreshCw,
} from 'react-icons/fi'
import { reviewsAPI } from '../../api/reviews'
import { ReviewSuggestion, ReviewSuggestionReason } from '../../types'

export const ReviewDashboardPage = () => {
  const navigate = useNavigate()
  const { colorMode } = useColorMode()
  const [priorityFilter, setPriorityFilter] = useState<string>('all')
  const [reasonFilter, setReasonFilter] = useState<string>('all')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['reviewSuggestions'],
    queryFn: () => reviewsAPI.getSuggestions(false),
    refetchInterval: 5 * 60 * 1000, // Refresh every 5 minutes
  })

  const getPriorityIcon = (priority: string) => {
    switch (priority) {
      case 'critical':
        return FiAlertTriangle
      case 'high':
        return FiAlertCircle
      case 'medium':
        return FiInfo
      case 'low':
        return FiCheckCircle
      default:
        return FiInfo
    }
  }

  const getPriorityColor = (priority: string): string => {
    switch (priority) {
      case 'critical':
        return 'red'
      case 'high':
        return 'orange'
      case 'medium':
        return 'yellow'
      case 'low':
        return 'blue'
      default:
        return 'gray'
    }
  }

  // Get background color for priority cards based on color mode
  const getPriorityBgColor = (priority: string): string => {
    const color = getPriorityColor(priority)
    // In dark mode, use gray.700 for all to avoid too-bright backgrounds
    // In light mode, use the standard .50 shade
    return colorMode === 'dark' ? 'gray.700' : `${color}.50`
  }

  const getReasonLabel = (reason: ReviewSuggestionReason): string => {
    switch (reason) {
      case 'trial_ending':
        return 'Trial Ending Today'
      case 'trial_ending_soon':
        return 'Trial Ending Soon'
      case 'likely_unused':
        return 'Likely Unused'
      case 'price_increased':
        return 'Price Increased'
      case 'expensive_unused':
        return 'Expensive & Unused'
      case 'duplicate_detected':
        return 'Duplicate Detected'
      default:
        return (reason as string).replace('_', ' ')
    }
  }

  const formatCurrency = (amount: number | null, currency: string) => {
    if (!amount) return 'N/A'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'EUR',
    }).format(amount)
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return null
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  // Filter suggestions
  const filteredSuggestions = data?.suggestions.filter((suggestion) => {
    if (priorityFilter !== 'all' && suggestion.priority !== priorityFilter) return false
    if (reasonFilter !== 'all' && suggestion.reason !== reasonFilter) return false
    return true
  })

  // Calculate potential savings
  const calculatePotentialSavings = () => {
    if (!data?.suggestions) return 0
    return data.suggestions.reduce((total, suggestion) => {
      if (!suggestion.amount) return total
      // Monthly normalization
      const monthlyAmount =
        suggestion.billing_cycle === 'yearly'
          ? suggestion.amount / 12
          : suggestion.billing_cycle === 'quarterly'
          ? suggestion.amount / 3
          : suggestion.billing_cycle === 'weekly'
          ? suggestion.amount * 4.33
          : suggestion.amount
      return total + monthlyAmount
    }, 0)
  }

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
          Failed to load review suggestions. Please try again.
        </Alert>
      </Container>
    )
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack align="stretch" spacing={8}>
        {/* Header */}
        <HStack justify="space-between" align="start">
          <Box>
            <Heading size="lg" mb={2}>
              Smart Review Dashboard
            </Heading>
            <Text color="text.subtle">
              AI-powered suggestions to optimize your subscriptions
            </Text>
          </Box>
          <Button
            leftIcon={<Icon as={FiRefreshCw} />}
            variant="outline"
            onClick={() => refetch()}
            size="sm"
          >
            Refresh
          </Button>
        </HStack>

        {/* Stats Cards */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiInfo} color="blue.500" />
                    <Text>Total Suggestions</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{data?.total_count || 0}</StatNumber>
                <StatHelpText>Subscriptions needing attention</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiAlertTriangle} color="red.500" />
                    <Text>Critical</Text>
                  </HStack>
                </StatLabel>
                <StatNumber color="red.600">{data?.critical_count || 0}</StatNumber>
                <StatHelpText>Urgent action required</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiAlertCircle} color="orange.500" />
                    <Text>High Priority</Text>
                  </HStack>
                </StatLabel>
                <StatNumber color="orange.600">{data?.high_priority_count || 0}</StatNumber>
                <StatHelpText>Important to review</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiCheckCircle} color="green.500" />
                    <Text>Potential Savings</Text>
                  </HStack>
                </StatLabel>
                <StatNumber color="green.600">
                  {new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: 'USD',
                  }).format(calculatePotentialSavings())}
                </StatNumber>
                <StatHelpText>Per month if cancelled</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Filters */}
        <Card>
          <CardBody>
            <HStack spacing={4} wrap="wrap">
              <Box>
                <Text fontSize="sm" fontWeight="semibold" mb={2}>
                  Priority:
                </Text>
                <Select
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                  size="sm"
                  w="200px"
                >
                  <option value="all">All Priorities</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </Select>
              </Box>

              <Box>
                <Text fontSize="sm" fontWeight="semibold" mb={2}>
                  Reason:
                </Text>
                <Select
                  value={reasonFilter}
                  onChange={(e) => setReasonFilter(e.target.value)}
                  size="sm"
                  w="200px"
                >
                  <option value="all">All Reasons</option>
                  <option value="trial_ending">Trial Ending</option>
                  <option value="trial_ending_soon">Trial Ending Soon</option>
                  <option value="expensive_unused">Expensive Unused</option>
                  <option value="likely_unused">Likely Unused</option>
                  <option value="duplicate_detected">Duplicates</option>
                  <option value="price_increased">Price Increased</option>
                </Select>
              </Box>

              {(priorityFilter !== 'all' || reasonFilter !== 'all') && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setPriorityFilter('all')
                    setReasonFilter('all')
                  }}
                  alignSelf="flex-end"
                >
                  Clear Filters
                </Button>
              )}
            </HStack>
          </CardBody>
        </Card>

        {/* Suggestions List */}
        {!filteredSuggestions || filteredSuggestions.length === 0 ? (
          <Card>
            <CardBody>
              <Alert status="success" borderRadius="md">
                <AlertIcon />
                <Box>
                  <Text fontWeight="semibold">
                    {data?.total_count === 0
                      ? 'All good! 🎉'
                      : 'No suggestions match your filters'}
                  </Text>
                  <Text fontSize="sm">
                    {data?.total_count === 0
                      ? 'No subscriptions need your attention right now.'
                      : 'Try adjusting your filters to see more suggestions.'}
                  </Text>
                </Box>
              </Alert>
            </CardBody>
          </Card>
        ) : (
          <VStack spacing={4} align="stretch">
            <Text fontSize="lg" fontWeight="semibold">
              Showing {filteredSuggestions.length} of {data?.total_count} suggestions
            </Text>

            {filteredSuggestions.map((suggestion) => (
              <Card
                key={suggestion.subscription_id}
                borderWidth="2px"
                borderColor={`${getPriorityColor(suggestion.priority)}.200`}
                bg={getPriorityBgColor(suggestion.priority)}
                cursor="pointer"
                _hover={{ shadow: 'lg', borderColor: `${getPriorityColor(suggestion.priority)}.400` }}
                onClick={() => navigate(`/subscriptions/${suggestion.subscription_id}`)}
              >
                <CardBody>
                  <VStack align="stretch" spacing={4}>
                    <HStack justify="space-between" align="start">
                      <HStack spacing={3}>
                        <Icon
                          as={getPriorityIcon(suggestion.priority)}
                          color={`${getPriorityColor(suggestion.priority)}.600`}
                          boxSize={6}
                        />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold" fontSize="xl">
                            {suggestion.provider}
                          </Text>
                          <HStack spacing={2} flexWrap="wrap">
                            <Badge
                              colorScheme={getPriorityColor(suggestion.priority)}
                              fontSize="sm"
                              px={2}
                              py={1}
                              textTransform="uppercase"
                            >
                              {suggestion.priority}
                            </Badge>
                            <Badge colorScheme="blue" fontSize="sm" px={2} py={1}>
                              {getReasonLabel(suggestion.reason)}
                            </Badge>
                          </HStack>
                        </VStack>
                      </HStack>
                      <Badge fontSize="lg" px={3} py={1} colorScheme="gray">
                        {formatCurrency(suggestion.amount, suggestion.currency)}/
                        {suggestion.billing_cycle}
                      </Badge>
                    </HStack>

                    <Text fontSize="md">
                      {suggestion.message}
                    </Text>

                    <Divider />

                    <HStack justify="space-between" fontSize="sm" color="text.subtle" wrap="wrap">
                      {suggestion.action_by_date && (
                        <HStack>
                          <Text fontWeight="semibold">Action by:</Text>
                          <Text>{formatDate(suggestion.action_by_date)}</Text>
                        </HStack>
                      )}
                      {suggestion.days_since_last_email !== null && (
                        <HStack>
                          <Text fontWeight="semibold">Last activity:</Text>
                          <Text>{suggestion.days_since_last_email} days ago</Text>
                        </HStack>
                      )}
                      {suggestion.price_change_amount !== null && (
                        <HStack>
                          <Text fontWeight="semibold">Price increase:</Text>
                          <Text color="red.600">
                            +{formatCurrency(suggestion.price_change_amount, suggestion.currency)}
                          </Text>
                        </HStack>
                      )}
                    </HStack>

                    <Button
                      colorScheme="blue"
                      size="sm"
                      alignSelf="flex-end"
                      onClick={(e) => {
                        e.stopPropagation()
                        navigate(`/subscriptions/${suggestion.subscription_id}`)
                      }}
                    >
                      View Details & Take Action
                    </Button>
                  </VStack>
                </CardBody>
              </Card>
            ))}
          </VStack>
        )}
      </VStack>
    </Container>
  )
}
