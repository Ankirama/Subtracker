import {
  Box,
  VStack,
  HStack,
  Text,
  Progress,
  Badge,
  IconButton,
  Icon,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  useColorModeValue,
} from '@chakra-ui/react'
import { FiEdit2, FiTrash2 } from 'react-icons/fi'
import { BudgetStatus } from '../../api/budgets'

interface BudgetCardProps {
  budgetStatus: BudgetStatus
  onEdit: () => void
  onDelete: () => void
}

export const BudgetCard = ({ budgetStatus, onEdit, onDelete }: BudgetCardProps) => {
  const cardBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'good':
        return 'green'
      case 'warning':
        return 'yellow'
      case 'exceeded':
        return 'red'
      default:
        return 'gray'
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'good':
        return 'On Track'
      case 'warning':
        return 'Approaching Limit'
      case 'exceeded':
        return 'Exceeded'
      default:
        return status
    }
  }

  const formatCurrency = (amount: number, currency: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(amount)
  }

  return (
    <Box
      bg={cardBg}
      borderWidth={1}
      borderColor={borderColor}
      borderRadius="lg"
      p={6}
      shadow="sm"
      _hover={{ shadow: 'md' }}
      transition="all 0.2s"
    >
      <VStack align="stretch" spacing={4}>
        {/* Header */}
        <HStack justify="space-between">
          <VStack align="start" spacing={0}>
            <Text fontWeight="bold" fontSize="lg">
              {budgetStatus.name}
            </Text>
            {budgetStatus.category && (
              <Badge colorScheme="blue" textTransform="capitalize">
                {budgetStatus.category}
              </Badge>
            )}
          </VStack>
          <HStack spacing={2}>
            <IconButton
              aria-label="Edit Budget"
              icon={<Icon as={FiEdit2} />}
              size="sm"
              variant="ghost"
              onClick={onEdit}
            />
            <IconButton
              aria-label="Delete Budget"
              icon={<Icon as={FiTrash2} />}
              size="sm"
              variant="ghost"
              colorScheme="red"
              onClick={onDelete}
            />
          </HStack>
        </HStack>

        {/* Status Badge */}
        <Badge
          colorScheme={getStatusColor(budgetStatus.status)}
          fontSize="sm"
          px={2}
          py={1}
          borderRadius="md"
          alignSelf="flex-start"
        >
          {getStatusLabel(budgetStatus.status)}
        </Badge>

        {/* Progress Bar */}
        <Box>
          <Progress
            value={Math.min(budgetStatus.percentage_used, 100)}
            colorScheme={getStatusColor(budgetStatus.status)}
            size="lg"
            borderRadius="md"
            hasStripe={budgetStatus.status === 'warning'}
            isAnimated={budgetStatus.status === 'warning'}
          />
          <Text fontSize="sm" color="text.subtle" mt={1}>
            {budgetStatus.percentage_used.toFixed(1)}% used
          </Text>
        </Box>

        {/* Spending Stats */}
        <HStack spacing={4} justify="space-between">
          <Stat size="sm">
            <StatLabel>Current Spending</StatLabel>
            <StatNumber fontSize="lg">
              {formatCurrency(budgetStatus.current_spending, budgetStatus.currency)}
            </StatNumber>
          </Stat>

          <Stat size="sm">
            <StatLabel>Limit</StatLabel>
            <StatNumber fontSize="lg">
              {formatCurrency(budgetStatus.limit_amount, budgetStatus.currency)}
            </StatNumber>
          </Stat>

          <Stat size="sm">
            <StatLabel>Remaining</StatLabel>
            <StatNumber fontSize="lg" color={budgetStatus.remaining < 0 ? 'red.500' : 'inherit'}>
              {formatCurrency(budgetStatus.remaining, budgetStatus.currency)}
            </StatNumber>
          </Stat>
        </HStack>

        {/* Period Info */}
        <HStack justify="space-between" fontSize="sm" color="text.subtle">
          <Text textTransform="capitalize">{budgetStatus.period} budget</Text>
          <Text>
            {new Date(budgetStatus.period_start).toLocaleDateString()} -{' '}
            {new Date(budgetStatus.period_end).toLocaleDateString()}
          </Text>
        </HStack>

        {/* Alert Info */}
        {budgetStatus.alert_enabled && (
          <Text fontSize="xs" color="gray.500">
            Alert threshold: {budgetStatus.alert_threshold}%
          </Text>
        )}
      </VStack>
    </Box>
  )
}
