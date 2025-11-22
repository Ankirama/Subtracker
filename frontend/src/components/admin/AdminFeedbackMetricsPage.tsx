import { useState, useEffect } from 'react'
import {
  Box,
  Heading,
  VStack,
  HStack,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  useToast,
  Alert,
  AlertIcon,
  Spinner,
  useColorModeValue,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Grid,
  GridItem,
  Text,
  Divider,
  Card,
  CardHeader,
  CardBody,
} from '@chakra-ui/react'
import { feedbackAPI } from '../../api/feedback'
import { DashboardMetrics, ProviderMetrics } from '../../types'

export const AdminFeedbackMetricsPage = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [loading, setLoading] = useState(true)

  const toast = useToast()
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const bgColor = useColorModeValue('white', 'gray.800')
  const cardBg = useColorModeValue('gray.50', 'gray.700')

  useEffect(() => {
    loadMetrics()
  }, [])

  const loadMetrics = async () => {
    try {
      setLoading(true)
      const data = await feedbackAPI.getDashboardMetrics()
      setMetrics(data)
    } catch (error) {
      toast({
        title: 'Error loading metrics',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setLoading(false)
    }
  }

  const formatPercentage = (value: number | null) => {
    if (value === null) return 'N/A'
    return `${(value * 100).toFixed(1)}%`
  }

  const formatNumber = (value: number | null) => {
    if (value === null) return 'N/A'
    return value.toFixed(1)
  }

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minH="400px">
        <Spinner size="xl" />
      </Box>
    )
  }

  if (!metrics) {
    return (
      <Alert status="error">
        <AlertIcon />
        Failed to load metrics
      </Alert>
    )
  }

  const { overall_metrics, provider_metrics } = metrics

  return (
    <Box>
      <VStack align="stretch" spacing={6}>
        <Heading size="lg">Feedback & Validation Metrics</Heading>

        {/* Overall Metrics Cards */}
        <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' }} gap={4}>
          <GridItem>
            <Card bg={cardBg} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>Total Feedback</StatLabel>
                  <StatNumber>{overall_metrics.total_feedback}</StatNumber>
                  <StatHelpText>All time</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>

          <GridItem>
            <Card bg={cardBg} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>High Confidence Success</StatLabel>
                  <StatNumber>
                    {formatPercentage(overall_metrics.high_confidence_success_rate)}
                  </StatNumber>
                  <StatHelpText>When AI is confident</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>

          <GridItem>
            <Card bg={cardBg} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>Low Confidence Success</StatLabel>
                  <StatNumber>
                    {formatPercentage(overall_metrics.low_confidence_success_rate)}
                  </StatNumber>
                  <StatHelpText>When AI is uncertain</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>

          <GridItem>
            <Card bg={cardBg} borderColor={borderColor} borderWidth="1px">
              <CardBody>
                <Stat>
                  <StatLabel>Providers Needing Update</StatLabel>
                  <StatNumber>{overall_metrics.providers_needing_update.length}</StatNumber>
                  <StatHelpText>Low success rate</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
        </Grid>

        {/* Providers Needing Update Alert */}
        {overall_metrics.providers_needing_update.length > 0 && (
          <Alert status="warning">
            <AlertIcon />
            <VStack align="start" spacing={1} flex={1}>
              <Text fontWeight="bold">Providers Needing Review</Text>
              <HStack spacing={2} flexWrap="wrap">
                {overall_metrics.providers_needing_update.map((provider) => (
                  <Badge key={provider} colorScheme="orange">
                    {provider}
                  </Badge>
                ))}
              </HStack>
            </VStack>
          </Alert>
        )}

        <Divider />

        {/* Provider Metrics Table */}
        <Box>
          <Heading size="md" mb={4}>
            Provider Performance
          </Heading>
          <Box bg={bgColor} borderWidth="1px" borderColor={borderColor} borderRadius="lg" overflowX="auto">
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Provider</Th>
                  <Th isNumeric>Total Feedback</Th>
                  <Th isNumeric>Helpful</Th>
                  <Th isNumeric>Not Helpful</Th>
                  <Th isNumeric>Success Rate</Th>
                  <Th isNumeric>Avg Time (min)</Th>
                  <Th isNumeric>Helpfulness</Th>
                  <Th isNumeric>Accuracy</Th>
                  <Th>Common Issues</Th>
                </Tr>
              </Thead>
              <Tbody>
                {provider_metrics.length === 0 ? (
                  <Tr>
                    <Td colSpan={9} textAlign="center" py={8}>
                      <Text color="gray.500">No provider data yet</Text>
                    </Td>
                  </Tr>
                ) : (
                  provider_metrics.map((provider: ProviderMetrics) => (
                    <Tr key={provider.provider_name}>
                      <Td fontWeight="medium">{provider.provider_name}</Td>
                      <Td isNumeric>{provider.total_feedback}</Td>
                      <Td isNumeric>
                        <Badge colorScheme="green">{provider.helpful_count}</Badge>
                      </Td>
                      <Td isNumeric>
                        <Badge colorScheme="red">{provider.not_helpful_count}</Badge>
                      </Td>
                      <Td isNumeric>
                        <Badge
                          colorScheme={
                            provider.success_rate === null
                              ? 'gray'
                              : provider.success_rate >= 0.8
                              ? 'green'
                              : provider.success_rate >= 0.6
                              ? 'yellow'
                              : 'red'
                          }
                        >
                          {formatPercentage(provider.success_rate)}
                        </Badge>
                      </Td>
                      <Td isNumeric>{formatNumber(provider.avg_time_minutes)}</Td>
                      <Td isNumeric>
                        {provider.avg_helpfulness !== null && (
                          <Badge
                            colorScheme={
                              provider.avg_helpfulness >= 4
                                ? 'green'
                                : provider.avg_helpfulness >= 3
                                ? 'yellow'
                                : 'red'
                            }
                          >
                            {formatNumber(provider.avg_helpfulness)}/5
                          </Badge>
                        )}
                        {provider.avg_helpfulness === null && (
                          <Text color="gray.500">N/A</Text>
                        )}
                      </Td>
                      <Td isNumeric>
                        {provider.avg_accuracy !== null && (
                          <Badge
                            colorScheme={
                              provider.avg_accuracy >= 4
                                ? 'green'
                                : provider.avg_accuracy >= 3
                                ? 'yellow'
                                : 'red'
                            }
                          >
                            {formatNumber(provider.avg_accuracy)}/5
                          </Badge>
                        )}
                        {provider.avg_accuracy === null && (
                          <Text color="gray.500">N/A</Text>
                        )}
                      </Td>
                      <Td>
                        {provider.common_issues.length > 0 ? (
                          <VStack align="start" spacing={1}>
                            {provider.common_issues.slice(0, 3).map((issue, idx) => (
                              <Badge key={idx} size="sm" colorScheme="purple">
                                {issue}
                              </Badge>
                            ))}
                            {provider.common_issues.length > 3 && (
                              <Text fontSize="xs" color="gray.500">
                                +{provider.common_issues.length - 3} more
                              </Text>
                            )}
                          </VStack>
                        ) : (
                          <Text color="gray.500" fontSize="sm">
                            None
                          </Text>
                        )}
                      </Td>
                    </Tr>
                  ))
                )}
              </Tbody>
            </Table>
          </Box>
        </Box>

        {/* Info Box */}
        <Alert status="info">
          <AlertIcon />
          <VStack align="start" spacing={1}>
            <Text fontWeight="bold">About These Metrics</Text>
            <Text fontSize="sm">
              These metrics help identify which providers have outdated cancellation instructions.
              Focus on providers with low success rates, low helpfulness ratings, or high "not helpful" counts.
            </Text>
          </VStack>
        </Alert>
      </VStack>
    </Box>
  )
}
