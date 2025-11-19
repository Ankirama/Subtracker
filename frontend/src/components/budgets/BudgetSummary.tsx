import {
  Box,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  useColorModeValue,
  Icon,
} from '@chakra-ui/react'
import { FiDollarSign, FiTrendingUp, FiAlertCircle } from 'react-icons/fi'
import { BudgetStatus } from '../../api/budgets'

interface BudgetSummaryProps {
  budgetStatuses: BudgetStatus[]
}

export const BudgetSummary = ({ budgetStatuses }: BudgetSummaryProps) => {
  const cardBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  // Calculate aggregate statistics
  const totalLimit = budgetStatuses.reduce((sum, b) => sum + b.limit_amount, 0)
  const totalSpending = budgetStatuses.reduce((sum, b) => sum + b.current_spending, 0)
  const totalRemaining = budgetStatuses.reduce((sum, b) => sum + b.remaining, 0)
  const avgPercentageUsed = budgetStatuses.length > 0
    ? budgetStatuses.reduce((sum, b) => sum + b.percentage_used, 0) / budgetStatuses.length
    : 0

  const budgetsAtRisk = budgetStatuses.filter(b => b.status === 'warning' || b.status === 'exceeded').length

  // Get currency from first budget (assuming all use same currency)
  const currency = budgetStatuses[0]?.currency || 'EUR'

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(amount)
  }

  return (
    <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
      <Box
        bg={cardBg}
        borderWidth={1}
        borderColor={borderColor}
        borderRadius="lg"
        p={5}
        shadow="sm"
      >
        <Stat>
          <StatLabel display="flex" alignItems="center" gap={2}>
            <Icon as={FiDollarSign} />
            Total Budget Limit
          </StatLabel>
          <StatNumber fontSize="2xl">{formatCurrency(totalLimit)}</StatNumber>
          <StatHelpText>{budgetStatuses.length} active budget{budgetStatuses.length !== 1 ? 's' : ''}</StatHelpText>
        </Stat>
      </Box>

      <Box
        bg={cardBg}
        borderWidth={1}
        borderColor={borderColor}
        borderRadius="lg"
        p={5}
        shadow="sm"
      >
        <Stat>
          <StatLabel display="flex" alignItems="center" gap={2}>
            <Icon as={FiTrendingUp} />
            Current Spending
          </StatLabel>
          <StatNumber fontSize="2xl">{formatCurrency(totalSpending)}</StatNumber>
          <StatHelpText>
            <StatArrow type={totalSpending > totalLimit ? 'increase' : 'decrease'} />
            {avgPercentageUsed.toFixed(1)}% of limit
          </StatHelpText>
        </Stat>
      </Box>

      <Box
        bg={cardBg}
        borderWidth={1}
        borderColor={borderColor}
        borderRadius="lg"
        p={5}
        shadow="sm"
      >
        <Stat>
          <StatLabel>Remaining Budget</StatLabel>
          <StatNumber fontSize="2xl" color={totalRemaining < 0 ? 'red.500' : 'green.500'}>
            {formatCurrency(totalRemaining)}
          </StatNumber>
          <StatHelpText>
            {totalRemaining >= 0 ? 'Within budget' : 'Over budget'}
          </StatHelpText>
        </Stat>
      </Box>

      <Box
        bg={cardBg}
        borderWidth={1}
        borderColor={borderColor}
        borderRadius="lg"
        p={5}
        shadow="sm"
      >
        <Stat>
          <StatLabel display="flex" alignItems="center" gap={2}>
            <Icon as={FiAlertCircle} />
            Budgets at Risk
          </StatLabel>
          <StatNumber fontSize="2xl" color={budgetsAtRisk > 0 ? 'orange.500' : 'green.500'}>
            {budgetsAtRisk}
          </StatNumber>
          <StatHelpText>
            {budgetsAtRisk === 0 ? 'All on track' : 'Need attention'}
          </StatHelpText>
        </Stat>
      </Box>
    </SimpleGrid>
  )
}
