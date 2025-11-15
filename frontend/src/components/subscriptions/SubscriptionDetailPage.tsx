import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Text,
  Button,
  Badge,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  Card,
  CardHeader,
  CardBody,
  Divider,
  Stack,
  Icon,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Code,
  Flex,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
} from '@chakra-ui/react'
import { FiArrowLeft, FiMail, FiCalendar, FiClock, FiInfo } from 'react-icons/fi'
import DOMPurify from 'dompurify'
import { subscriptionsAPI } from '../../api/subscriptions'
import { SubscriptionEmailLink } from '../../types'

export const SubscriptionDetailPage = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: subscription, isLoading, error } = useQuery({
    queryKey: ['subscription', id],
    queryFn: () => subscriptionsAPI.getById(id!),
    enabled: !!id,
  })

  const formatCurrency = (amount: number | null | undefined) => {
    if (!amount) return 'N/A'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: subscription?.currency || 'EUR',
    }).format(amount)
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const renderEmailBody = (link: SubscriptionEmailLink) => {
    if (!link.email.body_html && !link.email.body_text) {
      return <Text color="gray.500" fontSize="sm">No email body available</Text>
    }

    return (
      <Tabs colorScheme="blue" variant="enclosed">
        <TabList>
          <Tab>Source Code</Tab>
          {link.email.body_html && <Tab>Rendered HTML</Tab>}
        </TabList>
        <TabPanels>
          <TabPanel p={0} pt={4}>
            <Box bg="gray.50" p={4} borderRadius="md" maxH="400px" overflowY="auto">
              <Text whiteSpace="pre-wrap" fontFamily="monospace" fontSize="sm">
                {link.email.body_html || link.email.body_text || 'No content'}
              </Text>
            </Box>
          </TabPanel>
          {link.email.body_html && (
            <TabPanel p={0} pt={4}>
              <Box
                bg="white"
                p={4}
                borderRadius="md"
                border="1px solid"
                borderColor="gray.200"
                maxH="400px"
                overflowY="auto"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(link.email.body_html),
                }}
                sx={{
                  '& *': { fontSize: 'sm' },
                  '& img': { maxWidth: '100%', height: 'auto' },
                  '& a': { color: 'blue.600', textDecoration: 'underline' },
                  '& table': { borderCollapse: 'collapse', width: '100%' },
                  '& td, & th': { border: '1px solid #e2e8f0', padding: '8px' },
                }}
              />
            </TabPanel>
          )}
        </TabPanels>
      </Tabs>
    )
  }

  if (isLoading) {
    return (
      <Center h="100vh">
        <Spinner size="xl" color="blue.500" />
      </Center>
    )
  }

  if (error || !subscription) {
    return (
      <Container maxW="container.xl" py={8}>
        <Alert status="error">
          <AlertIcon />
          Failed to load subscription details. Please try again.
        </Alert>
      </Container>
    )
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack align="stretch" spacing={6}>
        {/* Back Button */}
        <Button
          leftIcon={<Icon as={FiArrowLeft} />}
          variant="ghost"
          alignSelf="flex-start"
          onClick={() => navigate('/subscriptions')}
        >
          Back to Subscriptions
        </Button>

        {/* Header */}
        <Box>
          <HStack justify="space-between" align="start">
            <Box>
              <Heading size="xl">{subscription.provider}</Heading>
              {subscription.custom_label && (
                <Text fontSize="lg" color="gray.600" mt={1}>
                  {subscription.custom_label}
                </Text>
              )}
            </Box>
            <Badge
              fontSize="md"
              px={3}
              py={1}
              borderRadius="full"
              colorScheme={subscription.is_active ? 'green' : 'gray'}
            >
              {subscription.is_active ? 'Active' : 'Inactive'}
            </Badge>
          </HStack>
        </Box>

        {/* Subscription Details Card */}
        <Card>
          <CardHeader>
            <Heading size="md">Subscription Details</Heading>
          </CardHeader>
          <CardBody>
            <Stack spacing={4}>
              <Flex wrap="wrap" gap={6}>
                <Stat>
                  <StatLabel>Amount</StatLabel>
                  <StatNumber>{formatCurrency(subscription.amount)}</StatNumber>
                  <StatHelpText textTransform="capitalize">{subscription.billing_cycle}</StatHelpText>
                </Stat>

                <Stat>
                  <StatLabel>Category</StatLabel>
                  <StatNumber fontSize="lg">
                    <Badge colorScheme="blue" textTransform="capitalize" fontSize="md">
                      {subscription.category}
                    </Badge>
                  </StatNumber>
                </Stat>

                <Stat>
                  <StatLabel>Next Renewal</StatLabel>
                  <StatNumber fontSize="lg">{formatDate(subscription.renewal_date)}</StatNumber>
                </Stat>
              </Flex>

              <Divider />

              <Stack spacing={2}>
                <HStack>
                  <Icon as={FiInfo} color="gray.500" />
                  <Text fontWeight="semibold">Extraction Method:</Text>
                  <Badge>{subscription.extraction_method || 'Unknown'}</Badge>
                </HStack>

                <HStack>
                  <Icon as={FiInfo} color="gray.500" />
                  <Text fontWeight="semibold">Confidence Score:</Text>
                  <Text>{subscription.confidence_score ? `${(subscription.confidence_score * 100).toFixed(0)}%` : 'N/A'}</Text>
                </HStack>

                {subscription.email_sender && (
                  <HStack>
                    <Icon as={FiMail} color="gray.500" />
                    <Text fontWeight="semibold">Email Sender:</Text>
                    <Text color="blue.600">{subscription.email_sender}</Text>
                  </HStack>
                )}

                {subscription.notes && (
                  <VStack align="start">
                    <Text fontWeight="semibold">Notes:</Text>
                    <Text color="gray.700">{subscription.notes}</Text>
                  </VStack>
                )}
              </Stack>

              <Divider />

              <HStack fontSize="sm" color="gray.600">
                <Icon as={FiCalendar} />
                <Text>First detected: {formatDate(subscription.first_detected_at)}</Text>
                <Text>•</Text>
                <Icon as={FiClock} />
                <Text>Last updated: {formatDate(subscription.updated_at)}</Text>
              </HStack>
            </Stack>
          </CardBody>
        </Card>

        {/* Source Emails */}
        <Card>
          <CardHeader>
            <HStack justify="space-between">
              <Heading size="md">Source Emails ({subscription.source_emails?.length || 0})</Heading>
              <Badge colorScheme="purple">
                AI-Extracted Data
              </Badge>
            </HStack>
          </CardHeader>
          <CardBody>
            {!subscription.source_emails || subscription.source_emails.length === 0 ? (
              <Text color="gray.500">No source emails found</Text>
            ) : (
              <Accordion allowMultiple>
                {subscription.source_emails.map((link, index) => (
                  <AccordionItem key={link.email.id}>
                    <h2>
                      <AccordionButton>
                        <Box flex="1" textAlign="left">
                          <VStack align="start" spacing={1}>
                            <HStack>
                              <Icon as={FiMail} color="blue.500" />
                              <Text fontWeight="semibold">{link.email.subject}</Text>
                              {link.extraction_role && (
                                <Badge colorScheme="purple" ml={2}>
                                  {link.extraction_role}
                                </Badge>
                              )}
                            </HStack>
                            <HStack fontSize="sm" color="gray.600">
                              <Text>From: {link.email.sender_name || link.email.sender}</Text>
                              <Text>•</Text>
                              <Text>{formatDateTime(link.email.date)}</Text>
                              {link.email.classification_confidence && (
                                <>
                                  <Text>•</Text>
                                  <Text>Confidence: {(link.email.classification_confidence * 100).toFixed(0)}%</Text>
                                </>
                              )}
                            </HStack>
                          </VStack>
                        </Box>
                        <AccordionIcon />
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack align="stretch" spacing={4}>
                        {/* Email Metadata */}
                        <Box p={3} bg="gray.50" borderRadius="md">
                          <Stack spacing={2} fontSize="sm">
                            <HStack>
                              <Text fontWeight="semibold">To:</Text>
                              <Text>{link.email.recipient}</Text>
                            </HStack>
                            <HStack>
                              <Text fontWeight="semibold">Date:</Text>
                              <Text>{formatDateTime(link.email.date)}</Text>
                            </HStack>
                          </Stack>
                        </Box>

                        {/* Extracted Data */}
                        {link.extraction_data && (
                          <Box>
                            <Text fontWeight="semibold" mb={2}>Extracted Data:</Text>
                            <Code
                              p={3}
                              borderRadius="md"
                              display="block"
                              whiteSpace="pre-wrap"
                              fontSize="sm"
                            >
                              {JSON.stringify(link.extraction_data, null, 2)}
                            </Code>
                          </Box>
                        )}

                        {/* Classification Reasoning */}
                        {link.email.classification_reasoning && (
                          <Box>
                            <Text fontWeight="semibold" mb={2}>AI Classification:</Text>
                            <Code
                              p={3}
                              borderRadius="md"
                              display="block"
                              whiteSpace="pre-wrap"
                              fontSize="sm"
                            >
                              {JSON.stringify(link.email.classification_reasoning, null, 2)}
                            </Code>
                          </Box>
                        )}

                        {/* Email Body */}
                        <Box>
                          <Text fontWeight="semibold" mb={2}>Email Content:</Text>
                          {renderEmailBody(link)}
                        </Box>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                ))}
              </Accordion>
            )}
          </CardBody>
        </Card>
      </VStack>
    </Container>
  )
}
