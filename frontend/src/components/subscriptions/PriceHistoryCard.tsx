import {
  Box,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Text,
  VStack,
  HStack,
  Badge,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  Divider,
  Icon,
  Spinner,
  Alert,
  AlertIcon,
  useColorModeValue,
} from '@chakra-ui/react'
import { FiTrendingUp, FiTrendingDown, FiDollarSign } from 'react-icons/fi'
import { useQuery } from '@tanstack/react-query'
import { subscriptionsAPI } from '../../api/subscriptions'
import { PriceHistory, PriceStatistics } from '../../types'
import { formatCurrency, formatDate } from '../../utils/formatters'

interface PriceHistoryCardProps {
  subscriptionId: string
}

export const PriceHistoryCard: React.FC<PriceHistoryCardProps> = ({ subscriptionId }) => {
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const increaseColor = useColorModeValue('red.500', 'red.300')
  const decreaseColor = useColorModeValue('green.500', 'green.300')
  const initialColor = useColorModeValue('blue.500', 'blue.300')

  // Fetch price history
  const { data: history, isLoading: historyLoading } = useQuery<PriceHistory[]>({
    queryKey: ['priceHistory', subscriptionId],
    queryFn: () => subscriptionsAPI.getPriceHistory(subscriptionId),
  })

  // Fetch price statistics
  const { data: stats, isLoading: statsLoading } = useQuery<PriceStatistics>({
    queryKey: ['priceStatistics', subscriptionId],
    queryFn: () => subscriptionsAPI.getPriceStatistics(subscriptionId),
  })

  const isLoading = historyLoading || statsLoading

  if (isLoading) {
    return (
      <Card>
        <CardBody>
          <VStack spacing={4}>
            <Spinner size="lg" />
            <Text>Loading price history...</Text>
          </VStack>
        </CardBody>
      </Card>
    )
  }

  if (!history || history.length === 0) {
    return (
      <Card>
        <CardHeader>
          <Heading size="md">Price History</Heading>
        </CardHeader>
        <CardBody>
          <Alert status="info">
            <AlertIcon />
            No price history available yet.
          </Alert>
        </CardBody>
      </Card>
    )
  }

  const getChangeIcon = (changeType: string) => {
    switch (changeType) {
      case 'increase':
        return FiTrendingUp
      case 'decrease':
        return FiTrendingDown
      default:
        return FiDollarSign
    }
  }

  const getChangeColor = (changeType: string) => {
    switch (changeType) {
      case 'increase':
        return increaseColor
      case 'decrease':
        return decreaseColor
      default:
        return initialColor
    }
  }

  const getChangeBadge = (changeType: string) => {
    switch (changeType) {
      case 'increase':
        return 'red'
      case 'decrease':
        return 'green'
      default:
        return 'blue'
    }
  }

  return (
    <Card>
      <CardHeader>
        <Heading size="md">Price History</Heading>
      </CardHeader>
      <CardBody>
        <VStack spacing={6} align="stretch">
          {/* Statistics Summary */}
          {stats && stats.total_changes > 0 && (
            <Box>
              <HStack spacing={4} mb={4}>
                <Stat>
                  <StatLabel>Total Changes</StatLabel>
                  <StatNumber>{stats.total_changes}</StatNumber>
                  <StatHelpText>
                    <HStack spacing={2}>
                      <Badge colorScheme="red">{stats.increases} increases</Badge>
                      <Badge colorScheme="green">{stats.decreases} decreases</Badge>
                    </HStack>
                  </StatHelpText>
                </Stat>

                <Stat>
                  <StatLabel>Avg Change</StatLabel>
                  <StatNumber>
                    {stats.average_change_percentage > 0 ? (
                      <HStack spacing={1}>
                        <StatArrow type="increase" />
                        <Text>{stats.average_change_percentage.toFixed(1)}%</Text>
                      </HStack>
                    ) : (
                      <HStack spacing={1}>
                        <StatArrow type="decrease" />
                        <Text>{Math.abs(stats.average_change_percentage).toFixed(1)}%</Text>
                      </HStack>
                    )}
                  </StatNumber>
                </Stat>

                {stats.original_price && stats.latest_price && (
                  <Stat>
                    <StatLabel>Price Change</StatLabel>
                    <StatNumber fontSize="lg">
                      {formatCurrency(stats.original_price, history[0].currency)} →{' '}
                      {formatCurrency(stats.latest_price, history[0].currency)}
                    </StatNumber>
                    <StatHelpText>
                      {stats.total_increase_amount > 0 && (
                        <Text color={increaseColor}>
                          +{formatCurrency(stats.total_increase_amount, history[0].currency)} total increase
                        </Text>
                      )}
                      {stats.total_decrease_amount > 0 && (
                        <Text color={decreaseColor}>
                          -{formatCurrency(stats.total_decrease_amount, history[0].currency)} total decrease
                        </Text>
                      )}
                    </StatHelpText>
                  </Stat>
                )}
              </HStack>
              <Divider my={4} />
            </Box>
          )}

          {/* Price History Timeline */}
          <VStack spacing={3} align="stretch">
            <Heading size="sm" mb={2}>Change History</Heading>
            {history.map((change, index) => (
              <Box
                key={change.id}
                p={4}
                borderWidth="1px"
                borderColor={borderColor}
                borderRadius="md"
                borderLeftWidth="4px"
                borderLeftColor={getChangeColor(change.change_type)}
              >
                <HStack justify="space-between" mb={2}>
                  <HStack spacing={3}>
                    <Icon
                      as={getChangeIcon(change.change_type)}
                      color={getChangeColor(change.change_type)}
                      boxSize={5}
                    />
                    <VStack align="start" spacing={0}>
                      <HStack>
                        <Text fontWeight="bold">
                          {change.old_amount !== null
                            ? `${formatCurrency(change.old_amount, change.currency)} → `
                            : ''}
                          {formatCurrency(change.new_amount, change.currency)}
                        </Text>
                        <Badge colorScheme={getChangeBadge(change.change_type)}>
                          {change.change_type}
                        </Badge>
                      </HStack>
                      {change.change_percentage !== null && (
                        <Text fontSize="sm" color="gray.500">
                          {change.change_type === 'increase' ? '+' : '-'}
                          {Math.abs(change.change_percentage).toFixed(1)}% change
                        </Text>
                      )}
                    </VStack>
                  </HStack>
                  <VStack align="end" spacing={0}>
                    <Text fontSize="sm" color="gray.500">
                      {formatDate(change.detected_at)}
                    </Text>
                    {change.detected_from && (
                      <Badge size="sm" variant="subtle">
                        {change.detected_from}
                      </Badge>
                    )}
                  </VStack>
                </HStack>
                {change.notes && (
                  <Text fontSize="sm" color="text.subtle" mt={2}>
                    {change.notes}
                  </Text>
                )}
              </Box>
            ))}
          </VStack>
        </VStack>
      </CardBody>
    </Card>
  )
}
