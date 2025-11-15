import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Text,
  Card,
  CardBody,
  SimpleGrid,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  Select,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Icon,
  useColorModeValue,
} from '@chakra-ui/react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { FiTrendingUp, FiPieChart, FiDollarSign, FiCalendar } from 'react-icons/fi'
import { subscriptionsAPI } from '../../api/subscriptions'
import { useState } from 'react'

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D']

export const AnalyticsPage = () => {
  const [timeRange, setTimeRange] = useState<'3m' | '6m' | '1y'>('6m')

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['subscriptionStats'],
    queryFn: subscriptionsAPI.getStats,
  })

  const { data: subscriptions } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => subscriptionsAPI.getAll({}),
  })

  const formatCurrency = (amount: number | undefined) => {
    if (!amount) return '€0.00'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount)
  }

  // Prepare data for category pie chart
  const categoryData = stats?.by_category
    ? Object.entries(stats.by_category).map(([name, data]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        value: data.total,
        count: data.count,
      }))
    : []

  // Prepare data for billing cycle distribution
  const billingCycleData = stats?.by_billing_cycle
    ? Object.entries(stats.by_billing_cycle).map(([name, count]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        count,
      }))
    : []

  // Generate monthly spending trend data (mock data for demonstration)
  const generateMonthlyTrend = () => {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    const monthlyCost = stats?.total_monthly_cost || 0

    return months.map((month, index) => ({
      month,
      cost: monthlyCost * (0.8 + Math.random() * 0.4), // Simulate variation
      subscriptions: (stats?.active_subscriptions || 0) + Math.floor(Math.random() * 3 - 1),
    }))
  }

  const monthlyTrendData = generateMonthlyTrend()

  // Calculate average subscription cost
  const averageSubscriptionCost =
    stats?.active_subscriptions && stats.active_subscriptions > 0
      ? (stats.total_monthly_cost || 0) / stats.active_subscriptions
      : 0

  // Find most expensive subscription
  const mostExpensive = subscriptions?.subscriptions.reduce((max, sub) => {
    return (sub.amount || 0) > (max.amount || 0) ? sub : max
  }, subscriptions?.subscriptions[0])

  const bgColor = useColorModeValue('white', 'gray.800')

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
          Failed to load analytics data. Please try again.
        </Alert>
      </Container>
    )
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack align="stretch" spacing={8}>
        {/* Header */}
        <HStack justify="space-between">
          <Box>
            <Heading size="lg">Analytics & Insights</Heading>
            <Text color="gray.600">Visualize your subscription spending patterns</Text>
          </Box>
          <Select
            maxW="150px"
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as '3m' | '6m' | '1y')}
          >
            <option value="3m">Last 3 months</option>
            <option value="6m">Last 6 months</option>
            <option value="1y">Last year</option>
          </Select>
        </HStack>

        {/* Key Metrics */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiDollarSign} color="green.500" />
                    <Text>Monthly Average</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{formatCurrency(stats?.total_monthly_cost)}</StatNumber>
                <StatHelpText>per month</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiTrendingUp} color="blue.500" />
                    <Text>Avg Per Subscription</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{formatCurrency(averageSubscriptionCost)}</StatNumber>
                <StatHelpText>average cost</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiPieChart} color="purple.500" />
                    <Text>Most Expensive</Text>
                  </HStack>
                </StatLabel>
                <StatNumber fontSize="lg">{mostExpensive?.provider || 'N/A'}</StatNumber>
                <StatHelpText>{formatCurrency(mostExpensive?.amount || 0)}</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiCalendar} color="orange.500" />
                    <Text>Yearly Total</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{formatCurrency(stats?.total_yearly_cost)}</StatNumber>
                <StatHelpText>annual cost</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Charts Grid */}
        <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
          {/* Monthly Spending Trend */}
          <Card>
            <CardBody>
              <Heading size="md" mb={4}>
                Monthly Spending Trend
              </Heading>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={monthlyTrendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip
                    formatter={(value: number) => formatCurrency(value)}
                    contentStyle={{ backgroundColor: bgColor }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="cost"
                    stroke="#3182CE"
                    strokeWidth={2}
                    name="Monthly Cost"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardBody>
          </Card>

          {/* Category Distribution */}
          <Card>
            <CardBody>
              <Heading size="md" mb={4}>
                Spending by Category
              </Heading>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={categoryData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) =>
                      `${name} (${(percent * 100).toFixed(0)}%)`
                    }
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {categoryData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number) => formatCurrency(value)}
                    contentStyle={{ backgroundColor: bgColor }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </CardBody>
          </Card>

          {/* Billing Cycle Distribution */}
          <Card>
            <CardBody>
              <Heading size="md" mb={4}>
                Subscriptions by Billing Cycle
              </Heading>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={billingCycleData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip contentStyle={{ backgroundColor: bgColor }} />
                  <Legend />
                  <Bar dataKey="count" fill="#48BB78" name="Subscriptions" />
                </BarChart>
              </ResponsiveContainer>
            </CardBody>
          </Card>

          {/* Category Breakdown Table */}
          <Card>
            <CardBody>
              <Heading size="md" mb={4}>
                Category Details
              </Heading>
              <VStack align="stretch" spacing={3}>
                {categoryData.map((category, index) => (
                  <HStack
                    key={category.name}
                    p={3}
                    borderWidth={1}
                    borderRadius="md"
                    justify="space-between"
                  >
                    <HStack>
                      <Box
                        w={3}
                        h={3}
                        borderRadius="sm"
                        bg={COLORS[index % COLORS.length]}
                      />
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="medium">{category.name}</Text>
                        <Text fontSize="sm" color="gray.600">
                          {category.count} subscription{category.count !== 1 ? 's' : ''}
                        </Text>
                      </VStack>
                    </HStack>
                    <VStack align="end" spacing={0}>
                      <Text fontWeight="bold">{formatCurrency(category.value)}</Text>
                      <Text fontSize="sm" color="gray.600">
                        /month
                      </Text>
                    </VStack>
                  </HStack>
                ))}
                {categoryData.length === 0 && (
                  <Text color="gray.500" textAlign="center" py={4}>
                    No subscription data available
                  </Text>
                )}
              </VStack>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Insights Section */}
        <Card bg="blue.50" borderColor="blue.200">
          <CardBody>
            <Heading size="md" mb={3}>
              💡 Insights & Recommendations
            </Heading>
            <VStack align="stretch" spacing={2}>
              {stats && stats.total_monthly_cost > 0 && (
                <>
                  <Text>
                    • You're spending{' '}
                    <Text as="span" fontWeight="bold">
                      {formatCurrency(stats.total_yearly_cost)}
                    </Text>{' '}
                    annually on subscriptions
                  </Text>
                  <Text>
                    • Your average subscription costs{' '}
                    <Text as="span" fontWeight="bold">
                      {formatCurrency(averageSubscriptionCost)}
                    </Text>{' '}
                    per month
                  </Text>
                  {stats.upcoming_renewals && stats.upcoming_renewals.length > 0 && (
                    <Text>
                      • You have{' '}
                      <Text as="span" fontWeight="bold">
                        {stats.upcoming_renewals.length}
                      </Text>{' '}
                      subscription{stats.upcoming_renewals.length !== 1 ? 's' : ''} renewing in the
                      next 30 days
                    </Text>
                  )}
                  {categoryData.length > 0 && (
                    <Text>
                      • Your top spending category is{' '}
                      <Text as="span" fontWeight="bold">
                        {categoryData[0].name}
                      </Text>{' '}
                      at {formatCurrency(categoryData[0].value)}/month
                    </Text>
                  )}
                </>
              )}
              {(!stats || stats.total_monthly_cost === 0) && (
                <Text color="gray.600">
                  Add subscriptions to see personalized insights and recommendations
                </Text>
              )}
            </VStack>
          </CardBody>
        </Card>
      </VStack>
    </Container>
  )
}
