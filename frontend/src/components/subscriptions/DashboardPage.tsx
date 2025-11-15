import { useQuery } from '@tanstack/react-query'
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
  Button,
  Icon,
} from '@chakra-ui/react'
import { FiDollarSign, FiCreditCard, FiCalendar, FiTrendingUp } from 'react-icons/fi'
import { subscriptionsAPI } from '../../api/subscriptions'
import { Link as RouterLink } from 'react-router-dom'

export const DashboardPage = () => {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['subscriptionStats'],
    queryFn: subscriptionsAPI.getStats,
  })

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
          Failed to load dashboard data. Please try again.
        </Alert>
      </Container>
    )
  }

  const formatCurrency = (amount: number | undefined) => {
    if (!amount) return '€0.00'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount)
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack align="stretch" spacing={8}>
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>
            Dashboard
          </Heading>
          <Text color="gray.600">Overview of your subscriptions</Text>
        </Box>

        {/* Stats Cards */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiCreditCard} color="blue.500" />
                    <Text>Total Subscriptions</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{stats?.total_subscriptions || 0}</StatNumber>
                <StatHelpText>
                  {stats?.active_subscriptions || 0} active
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiDollarSign} color="green.500" />
                    <Text>Monthly Cost</Text>
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
                    <Icon as={FiTrendingUp} color="purple.500" />
                    <Text>Yearly Cost</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{formatCurrency(stats?.total_yearly_cost)}</StatNumber>
                <StatHelpText>per year</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiCalendar} color="orange.500" />
                    <Text>Upcoming Renewals</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{stats?.upcoming_renewals?.length || 0}</StatNumber>
                <StatHelpText>next 30 days</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Category Breakdown */}
        {stats?.by_category && Object.keys(stats.by_category).length > 0 && (
          <Card>
            <CardBody>
              <Heading size="md" mb={4}>
                By Category
              </Heading>
              <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                {Object.entries(stats.by_category).map(([category, data]) => (
                  <Box key={category} p={4} borderWidth={1} borderRadius="md">
                    <HStack justify="space-between" mb={2}>
                      <Badge colorScheme="blue" textTransform="capitalize">
                        {category}
                      </Badge>
                      <Text fontWeight="bold">{data.count}</Text>
                    </HStack>
                    <Text fontSize="sm" color="gray.600">
                      {formatCurrency(data.total)}/month
                    </Text>
                  </Box>
                ))}
              </SimpleGrid>
            </CardBody>
          </Card>
        )}

        {/* Upcoming Renewals */}
        {stats?.upcoming_renewals && stats.upcoming_renewals.length > 0 && (
          <Card>
            <CardBody>
              <Heading size="md" mb={4}>
                Upcoming Renewals
              </Heading>
              <VStack align="stretch" spacing={3}>
                {stats.upcoming_renewals.slice(0, 5).map((subscription) => (
                  <Box
                    key={subscription.id}
                    p={4}
                    borderWidth={1}
                    borderRadius="md"
                    _hover={{ bg: 'gray.50' }}
                  >
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="bold">{subscription.provider}</Text>
                        <Text fontSize="sm" color="gray.600">
                          {subscription.renewal_date
                            ? new Date(subscription.renewal_date).toLocaleDateString()
                            : 'No date set'}
                        </Text>
                      </VStack>
                      <VStack align="end" spacing={1}>
                        <Text fontWeight="bold">
                          {formatCurrency(subscription.amount || 0)}
                        </Text>
                        <Badge colorScheme="blue" textTransform="capitalize">
                          {subscription.billing_cycle}
                        </Badge>
                      </VStack>
                    </HStack>
                  </Box>
                ))}
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Quick Actions */}
        <HStack>
          <Button as={RouterLink} to="/subscriptions" colorScheme="blue">
            View All Subscriptions
          </Button>
          <Button as={RouterLink} to="/mailboxes" variant="outline">
            Manage Mailboxes
          </Button>
        </HStack>
      </VStack>
    </Container>
  )
}
