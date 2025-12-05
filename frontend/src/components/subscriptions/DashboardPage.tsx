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
import { FiDollarSign, FiCreditCard, FiCalendar, FiTrendingUp, FiBell } from 'react-icons/fi'
import { useTranslation } from 'react-i18next'
import { subscriptionsAPI } from '../../api/subscriptions'
import { notificationsApi } from '../../api/notifications'
import { Link as RouterLink } from 'react-router-dom'
import { SubscriptionStats } from '../../types'

export const DashboardPage = () => {
  const { t } = useTranslation()
  const { data: stats, isLoading, error, refetch: refetchStats } = useQuery<SubscriptionStats>({
    queryKey: ['subscriptionStats'],
    queryFn: () => subscriptionsAPI.getStats(),
  })

  const { data: upcomingRenewals, refetch: refetchRenewals } = useQuery({
    queryKey: ['upcomingRenewals'],
    queryFn: () => notificationsApi.getUpcomingRenewals(30),
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
          {t('dashboard:errors.loadFailed')}
        </Alert>
      </Container>
    )
  }

  const formatCurrency = (amount: number | undefined, currency: string = 'EUR') => {
    if (!amount) return '€0.00'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(amount)
  }

  const getUrgencyColor = (daysUntil: number) => {
    if (daysUntil <= 3) return 'red'
    if (daysUntil <= 7) return 'orange'
    if (daysUntil <= 14) return 'yellow'
    return 'green'
  }

  const handleRefresh = async () => {
    await Promise.all([refetchStats(), refetchRenewals()])
  }

  return (
    <Container maxW="container.xl" py={8}>
        <VStack align="stretch" spacing={8}>
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>
            {t('dashboard:title')}
          </Heading>
          <Text color="text.subtle">{t('dashboard:subtitle')}</Text>
        </Box>

        {/* Stats Cards */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiCreditCard} color="blue.500" />
                    <Text>{t('dashboard:stats.totalSubscriptions')}</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{stats?.total_subscriptions || 0}</StatNumber>
                <StatHelpText>
                  {stats?.active_subscriptions || 0} {t('dashboard:stats.active')}
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
                    <Text>{t('dashboard:stats.monthlyCost')}</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{formatCurrency(stats?.total_monthly_cost)}</StatNumber>
                <StatHelpText>{t('dashboard:stats.perMonth')}</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiTrendingUp} color="purple.500" />
                    <Text>{t('dashboard:stats.yearlyCost')}</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{formatCurrency(stats?.total_yearly_cost)}</StatNumber>
                <StatHelpText>{t('dashboard:stats.perYear')}</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>
                  <HStack>
                    <Icon as={FiCalendar} color="orange.500" />
                    <Text>{t('dashboard:stats.upcomingRenewals')}</Text>
                  </HStack>
                </StatLabel>
                <StatNumber>{upcomingRenewals?.length || 0}</StatNumber>
                <StatHelpText>{t('dashboard:stats.next30Days')}</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>


        {/* Category Breakdown */}
        {stats?.by_category && Object.keys(stats.by_category).length > 0 && (
          <Card>
            <CardBody>
              <Heading size="md" mb={4}>
                {t('dashboard:byCategory')}
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
                    <Text fontSize="sm" color="text.subtle">
                      {formatCurrency(data.total)}{t('dashboard:monthSuffix')}
                    </Text>
                  </Box>
                ))}
              </SimpleGrid>
            </CardBody>
          </Card>
        )}

        {/* Upcoming Renewals */}
        {upcomingRenewals && upcomingRenewals.length > 0 && (
          <Card>
            <CardBody>
              <HStack justify="space-between" mb={4}>
                <Heading size="md">{t('dashboard:renewals.title')}</Heading>
                <Button
                  as={RouterLink}
                  to="/notifications/settings"
                  leftIcon={<Icon as={FiBell} />}
                  size="sm"
                  variant="ghost"
                  colorScheme="blue"
                >
                  {t('dashboard:renewals.configureReminders')}
                </Button>
              </HStack>
              <VStack align="stretch" spacing={3}>
                {upcomingRenewals.slice(0, 5).map((renewal) => (
                  <Box
                    key={renewal.subscription_id}
                    p={4}
                    borderWidth={1}
                    borderRadius="md"
                    borderLeftWidth={4}
                    borderLeftColor={`${getUrgencyColor(renewal.days_until_renewal)}.500`}
                    _hover={{ bg: 'gray.50' }}
                  >
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1} flex={1}>
                        <Text fontWeight="bold">{renewal.provider}</Text>
                        <HStack spacing={2}>
                          <Badge colorScheme={getUrgencyColor(renewal.days_until_renewal)}>
                            {renewal.days_until_renewal === 0 && t('dashboard:renewals.today')}
                            {renewal.days_until_renewal === 1 && t('dashboard:renewals.tomorrow')}
                            {renewal.days_until_renewal > 1 && `${renewal.days_until_renewal} ${t('dashboard:renewals.days')}`}
                          </Badge>
                          <Text fontSize="sm" color="text.subtle">
                            {new Date(renewal.renewal_date).toLocaleDateString()}
                          </Text>
                        </HStack>
                      </VStack>
                      <VStack align="end" spacing={1}>
                        <Text fontWeight="bold" fontSize="lg">
                          {formatCurrency(renewal.amount, renewal.currency)}
                        </Text>
                        <Badge colorScheme="blue" textTransform="capitalize">
                          {renewal.billing_cycle}
                        </Badge>
                      </VStack>
                    </HStack>
                  </Box>
                ))}
                {upcomingRenewals.length > 5 && (
                  <Button
                    as={RouterLink}
                    to="/subscriptions"
                    variant="ghost"
                    colorScheme="blue"
                    size="sm"
                  >
                    {t('dashboard:renewals.viewAll', { count: upcomingRenewals.length })}
                  </Button>
                )}
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Quick Actions */}
        <HStack>
          <Button as={RouterLink} to="/subscriptions" colorScheme="blue">
            {t('dashboard:actions.viewAllSubscriptions')}
          </Button>
          <Button as={RouterLink} to="/mailboxes" variant="outline">
            {t('dashboard:actions.manageMailboxes')}
          </Button>
        </HStack>
        </VStack>
    </Container>
  )
}
