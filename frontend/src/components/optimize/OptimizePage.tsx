import { useState, useEffect } from 'react'
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
  CardHeader,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  Badge,
  Icon,
  useColorModeValue,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  SimpleGrid,
  Button,
} from '@chakra-ui/react'
import {
  FiTrendingDown,
  FiAlertCircle,
  FiRefreshCw,
  FiCheckCircle,
  FiXCircle,
} from 'react-icons/fi'
import { optimizeApi, Recommendation } from '../../api/optimize'

const PRIORITY_COLORS = {
  high: 'red',
  medium: 'orange',
  low: 'green',
}

const RECOMMENDATION_ICONS: Record<string, string> = {
  duplicate_consolidation: '🔄',
  duplicate_review: '📋',
  unused_subscription: '⏸️',
  family_plan_upgrade: '👨‍👩‍👧‍👦',
  annual_billing_savings: '📅',
  alternative_provider: '🔄',
  cost_reduction: '💰',
}

export const OptimizePage = () => {
  const cardBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const insightBg = useColorModeValue('blue.50', 'blue.900')

  const { data, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: ['optimization'],
    queryFn: optimizeApi.getRecommendations,
    refetchOnWindowFocus: false,
  })

  if (isLoading) {
    return (
      <Center h="100vh">
        <VStack spacing={4}>
          <Spinner size="xl" color="blue.500" />
          <Text color="gray.600">Analyzing your subscriptions...</Text>
        </VStack>
      </Center>
    )
  }

  if (error) {
    return (
      <Container maxW="container.xl" py={8}>
        <Alert status="error">
          <AlertIcon />
          Failed to load optimization recommendations. Please try again.
        </Alert>
      </Container>
    )
  }

  const recommendations = data?.recommendations || []
  const insights = data?.insights || []
  const potentialSavings = data?.potential_savings || 0
  const totalRecommendations = data?.total_recommendations || 0

  // Group recommendations by priority
  const highPriority = recommendations.filter((r) => r.priority === 'high')
  const mediumPriority = recommendations.filter((r) => r.priority === 'medium')
  const lowPriority = recommendations.filter((r) => r.priority === 'low')

  return (
    <Container maxW="container.xl" py={8}>
      <VStack align="stretch" spacing={6}>
        {/* Header */}
        <Box>
          <HStack justify="space-between" mb={2}>
            <Box>
              <Heading size="lg">🤖 AI Optimization</Heading>
              <Text color="gray.600">
                Personalized recommendations to save money and optimize your subscriptions
              </Text>
            </Box>
            <Button
              leftIcon={<Icon as={FiRefreshCw} />}
              onClick={() => refetch()}
              isLoading={isRefetching}
              loadingText="Analyzing..."
            >
              Re-analyze
            </Button>
          </HStack>
        </Box>

        {/* Stats Cards */}
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
          <Card bg={cardBg} borderColor={borderColor}>
            <CardBody>
              <Stat>
                <StatLabel>Potential Savings</StatLabel>
                <StatNumber color="green.500">€{potentialSavings.toFixed(2)}</StatNumber>
                <StatHelpText>€{(potentialSavings * 12).toFixed(2)}/year</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card bg={cardBg} borderColor={borderColor}>
            <CardBody>
              <Stat>
                <StatLabel>Total Recommendations</StatLabel>
                <StatNumber>{totalRecommendations}</StatNumber>
                <StatHelpText>
                  {highPriority.length > 0 && (
                    <Badge colorScheme="red" mr={2}>
                      {highPriority.length} High Priority
                    </Badge>
                  )}
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card bg={cardBg} borderColor={borderColor}>
            <CardBody>
              <Stat>
                <StatLabel>Analysis Status</StatLabel>
                <StatNumber fontSize="lg">
                  <Icon as={FiCheckCircle} color="green.500" mr={2} />
                  Complete
                </StatNumber>
                <StatHelpText>
                  {data?.analyzed_at &&
                    `Updated ${new Date(data.analyzed_at).toLocaleString()}`}
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* AI Insights */}
        {insights.length > 0 && (
          <Card bg={insightBg} borderColor="blue.300" borderWidth={2}>
            <CardHeader>
              <Heading size="md">💡 Key Insights</Heading>
            </CardHeader>
            <CardBody pt={0}>
              <VStack align="stretch" spacing={2}>
                {insights.map((insight, index) => (
                  <Text key={index} fontSize="sm">
                    {insight}
                  </Text>
                ))}
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* No Recommendations */}
        {recommendations.length === 0 && (
          <Card bg={cardBg}>
            <CardBody>
              <Center py={8}>
                <VStack spacing={4}>
                  <Icon as={FiCheckCircle} boxSize={12} color="green.500" />
                  <Heading size="md">All Optimized! 🎉</Heading>
                  <Text color="gray.600" textAlign="center">
                    Your subscriptions are well-optimized. Check back later for new recommendations.
                  </Text>
                </VStack>
              </Center>
            </CardBody>
          </Card>
        )}

        {/* High Priority Recommendations */}
        {highPriority.length > 0 && (
          <Box>
            <Heading size="md" mb={4} color="red.500">
              🚨 High Priority Actions
            </Heading>
            <VStack align="stretch" spacing={4}>
              {highPriority.map((rec, index) => (
                <RecommendationCard key={index} recommendation={rec} />
              ))}
            </VStack>
          </Box>
        )}

        {/* Medium Priority Recommendations */}
        {mediumPriority.length > 0 && (
          <Box>
            <Heading size="md" mb={4} color="orange.500">
              ⚠️ Medium Priority Suggestions
            </Heading>
            <VStack align="stretch" spacing={4}>
              {mediumPriority.map((rec, index) => (
                <RecommendationCard key={index} recommendation={rec} />
              ))}
            </VStack>
          </Box>
        )}

        {/* Low Priority Recommendations */}
        {lowPriority.length > 0 && (
          <Box>
            <Heading size="md" mb={4} color="green.500">
              💚 Nice to Have
            </Heading>
            <VStack align="stretch" spacing={4}>
              {lowPriority.map((rec, index) => (
                <RecommendationCard key={index} recommendation={rec} />
              ))}
            </VStack>
          </Box>
        )}
      </VStack>
    </Container>
  )
}

// Recommendation Card Component
const RecommendationCard = ({ recommendation }: { recommendation: Recommendation }) => {
  const cardBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  const icon = RECOMMENDATION_ICONS[recommendation.type] || '💡'
  const priorityColor = PRIORITY_COLORS[recommendation.priority]

  return (
    <Card bg={cardBg} borderColor={borderColor} _hover={{ shadow: 'lg' }} transition="all 0.2s">
      <CardBody>
        <VStack align="stretch" spacing={3}>
          <HStack justify="space-between">
            <HStack spacing={3}>
              <Text fontSize="2xl">{icon}</Text>
              <Box>
                <Text fontWeight="bold" fontSize="lg">
                  {recommendation.title}
                </Text>
              </Box>
            </HStack>
            <HStack>
              {recommendation.potential_savings > 0 && (
                <Badge colorScheme="green" fontSize="md" px={3} py={1}>
                  Save €{recommendation.potential_savings.toFixed(2)}/mo
                </Badge>
              )}
              <Badge colorScheme={priorityColor} textTransform="uppercase">
                {recommendation.priority}
              </Badge>
            </HStack>
          </HStack>

          <Text color="gray.600">{recommendation.description}</Text>

          {/* Action badge */}
          <HStack spacing={2}>
            <Icon as={FiAlertCircle} color="blue.500" />
            <Text fontSize="sm" color="blue.600" fontWeight="medium">
              Action: {recommendation.action.replace(/_/g, ' ')}
            </Text>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  )
}
