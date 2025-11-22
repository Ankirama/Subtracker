import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Card,
  CardHeader,
  CardBody,
  Heading,
  VStack,
  HStack,
  Text,
  Button,
  Badge,
  Icon,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  Divider,
  Flex,
} from '@chakra-ui/react'
import {
  FiAlertTriangle,
  FiAlertCircle,
  FiInfo,
  FiClock,
  FiTrendingUp,
  FiCopy,
  FiChevronRight,
} from 'react-icons/fi'
import { reviewsAPI } from '../../api/reviews'
import { ReviewSuggestion, ReviewSuggestionReason } from '../../types'

interface ReviewSuggestionsCardProps {
  maxSuggestions?: number
  compact?: boolean
}

export const ReviewSuggestionsCard = ({
  maxSuggestions = 5,
  compact = false,
}: ReviewSuggestionsCardProps) => {
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery({
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
        return FiClock
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

  const getReasonIcon = (reason: ReviewSuggestionReason) => {
    switch (reason) {
      case 'trial_ending':
      case 'trial_ending_soon':
        return FiClock
      case 'likely_unused':
        return FiInfo
      case 'price_increased':
        return FiTrendingUp
      case 'expensive_unused':
        return FiAlertCircle
      case 'duplicate_detected':
        return FiCopy
      default:
        return FiInfo
    }
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
    })
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Heading size="md">Smart Review Suggestions</Heading>
        </CardHeader>
        <CardBody>
          <Center py={8}>
            <Spinner size="lg" color="blue.500" />
          </Center>
        </CardBody>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <Heading size="md">Smart Review Suggestions</Heading>
        </CardHeader>
        <CardBody>
          <Alert status="error">
            <AlertIcon />
            Failed to load review suggestions
          </Alert>
        </CardBody>
      </Card>
    )
  }

  if (!data || data.total_count === 0) {
    return (
      <Card>
        <CardHeader>
          <Heading size="md">Smart Review Suggestions</Heading>
        </CardHeader>
        <CardBody>
          <Alert status="success" borderRadius="md">
            <AlertIcon />
            <Box>
              <Text fontWeight="semibold">All good! 🎉</Text>
              <Text fontSize="sm">
                No subscriptions need your attention right now. We'll notify you if anything changes.
              </Text>
            </Box>
          </Alert>
        </CardBody>
      </Card>
    )
  }

  const displayedSuggestions = data.suggestions.slice(0, maxSuggestions)
  const hasMore = data.suggestions.length > maxSuggestions

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={1}>
            <Heading size="md">Smart Review Suggestions</Heading>
            <HStack spacing={2}>
              {data.critical_count > 0 && (
                <Badge colorScheme="red" fontSize="xs">
                  {data.critical_count} Critical
                </Badge>
              )}
              {data.high_priority_count > 0 && (
                <Badge colorScheme="orange" fontSize="xs">
                  {data.high_priority_count} High Priority
                </Badge>
              )}
              <Badge colorScheme="gray" fontSize="xs">
                {data.total_count} Total
              </Badge>
            </HStack>
          </VStack>
        </HStack>
      </CardHeader>
      <CardBody>
        <VStack spacing={3} align="stretch">
          {displayedSuggestions.map((suggestion) => (
            <Box
              key={suggestion.subscription_id}
              p={4}
              borderWidth="1px"
              borderRadius="md"
              borderColor={`${getPriorityColor(suggestion.priority)}.200`}
              bg={`${getPriorityColor(suggestion.priority)}.50`}
              cursor="pointer"
              _hover={{ shadow: 'md', borderColor: `${getPriorityColor(suggestion.priority)}.300` }}
              onClick={() => navigate(`/subscriptions/${suggestion.subscription_id}`)}
            >
              <VStack align="stretch" spacing={2}>
                <HStack justify="space-between" align="start">
                  <HStack spacing={2} flex="1">
                    <Icon
                      as={getPriorityIcon(suggestion.priority)}
                      color={`${getPriorityColor(suggestion.priority)}.600`}
                      boxSize={5}
                    />
                    <VStack align="start" spacing={0} flex="1">
                      <Text fontWeight="bold" fontSize="md">
                        {suggestion.provider}
                      </Text>
                      <HStack spacing={2} flexWrap="wrap">
                        <Badge
                          colorScheme={getPriorityColor(suggestion.priority)}
                          fontSize="xs"
                          textTransform="uppercase"
                        >
                          {suggestion.priority}
                        </Badge>
                        <Badge
                          colorScheme="blue"
                          fontSize="xs"
                          variant="subtle"
                        >
                          <HStack spacing={1}>
                            <Icon as={getReasonIcon(suggestion.reason)} boxSize={3} />
                            <Text>{getReasonLabel(suggestion.reason)}</Text>
                          </HStack>
                        </Badge>
                      </HStack>
                    </VStack>
                  </HStack>
                  <Icon as={FiChevronRight} color="gray.400" />
                </HStack>

                <Text fontSize="sm" color="gray.700">
                  {suggestion.message}
                </Text>

                {!compact && (
                  <>
                    <Divider />
                    <Flex justify="space-between" fontSize="xs" color="text.subtle" flexWrap="wrap" gap={2}>
                      <HStack>
                        <Text fontWeight="semibold">Cost:</Text>
                        <Text>
                          {formatCurrency(suggestion.amount, suggestion.currency)}/
                          {suggestion.billing_cycle}
                        </Text>
                      </HStack>
                      {suggestion.action_by_date && (
                        <HStack>
                          <Icon as={FiClock} />
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
                          <Icon as={FiTrendingUp} color="red.500" />
                          <Text fontWeight="semibold">Increase:</Text>
                          <Text color="red.600">
                            +{formatCurrency(suggestion.price_change_amount, suggestion.currency)}
                          </Text>
                        </HStack>
                      )}
                    </Flex>
                  </>
                )}
              </VStack>
            </Box>
          ))}

          {hasMore && (
            <Button
              variant="ghost"
              colorScheme="blue"
              size="sm"
              onClick={() => navigate('/subscriptions')}
            >
              View {data.total_count - maxSuggestions} more suggestions
            </Button>
          )}
        </VStack>
      </CardBody>
    </Card>
  )
}
