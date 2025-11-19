import {
  Box,
  Heading,
  SimpleGrid,
  Text,
  useColorModeValue,
} from '@chakra-ui/react'
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts'
import { BudgetStatus } from '../../api/budgets'

interface BudgetChartsProps {
  budgetStatuses: BudgetStatus[]
}

const COLORS = ['#3182CE', '#38A169', '#D69E2E', '#E53E3E', '#805AD5', '#DD6B20', '#319795', '#D53F8C']

export const BudgetCharts = ({ budgetStatuses }: BudgetChartsProps) => {
  const cardBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const textColor = useColorModeValue('gray.600', 'gray.400')

  // Prepare data for pie chart (spending by budget)
  const spendingByBudget = budgetStatuses.map(budget => ({
    name: budget.name,
    value: budget.current_spending,
    percentage: budget.percentage_used,
  })).filter(item => item.value > 0) // Only show budgets with spending

  // Prepare data for bar chart (usage comparison)
  const usageComparison = budgetStatuses.map(budget => ({
    name: budget.name.length > 15 ? budget.name.substring(0, 15) + '...' : budget.name,
    spending: budget.current_spending,
    limit: budget.limit_amount,
    remaining: Math.max(0, budget.remaining),
  }))

  const currency = budgetStatuses[0]?.currency || 'EUR'

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value)
  }

  if (budgetStatuses.length === 0) {
    return null
  }

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
      {/* Spending Distribution Pie Chart */}
      <Box
        bg={cardBg}
        borderWidth={1}
        borderColor={borderColor}
        borderRadius="lg"
        p={6}
        shadow="sm"
      >
        <Heading size="md" mb={4}>
          Spending Distribution
        </Heading>
        {spendingByBudget.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={spendingByBudget}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {spendingByBudget.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => formatCurrency(value as number)} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <Text color={textColor} textAlign="center" py={8}>
            No spending data yet
          </Text>
        )}
      </Box>

      {/* Budget Usage Bar Chart */}
      <Box
        bg={cardBg}
        borderWidth={1}
        borderColor={borderColor}
        borderRadius="lg"
        p={6}
        shadow="sm"
      >
        <Heading size="md" mb={4}>
          Budget Usage Comparison
        </Heading>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={usageComparison}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" fontSize={12} />
            <YAxis tickFormatter={formatCurrency} fontSize={12} />
            <Tooltip formatter={(value) => formatCurrency(value as number)} />
            <Legend />
            <Bar dataKey="spending" fill="#3182CE" name="Current Spending" />
            <Bar dataKey="limit" fill="#CBD5E0" name="Budget Limit" />
          </BarChart>
        </ResponsiveContainer>
      </Box>
    </SimpleGrid>
  )
}
