import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Box,
  VStack,
  HStack,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  Button,
  Alert,
  AlertIcon,
  Text,
  Badge,
  Card,
  CardBody,
  CardHeader,
  Heading,
  useToast,
  Divider,
  Code,
  Spinner,
} from '@chakra-ui/react'
import { aiSandboxAPI } from '../../api/aiSandbox'
import { EmailTestRequest, ClassificationTestResponse, ExtractionTestResponse } from '../../types'

export const ManualTestTab = () => {
  const toast = useToast()
  const [emailData, setEmailData] = useState<EmailTestRequest>({
    subject: '',
    sender: '',
    sender_name: '',
    body_text: '',
    body_html: '',
  })

  const [classificationResult, setClassificationResult] = useState<ClassificationTestResponse | null>(null)
  const [extractionResult, setExtractionResult] = useState<ExtractionTestResponse | null>(null)

  const classificationMutation = useMutation({
    mutationFn: aiSandboxAPI.testClassification,
    onSuccess: (data) => {
      setClassificationResult(data)
      toast({
        title: 'Classification test completed',
        status: 'success',
        duration: 3000,
      })
    },
    onError: () => {
      toast({
        title: 'Classification test failed',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const extractionMutation = useMutation({
    mutationFn: aiSandboxAPI.testExtraction,
    onSuccess: (data) => {
      setExtractionResult(data)
      toast({
        title: 'Extraction test completed',
        status: 'success',
        duration: 3000,
      })
    },
    onError: () => {
      toast({
        title: 'Extraction test failed',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const handleTestClassification = () => {
    if (!emailData.subject || !emailData.sender) {
      toast({
        title: 'Subject and sender are required',
        status: 'warning',
        duration: 3000,
      })
      return
    }
    classificationMutation.mutate(emailData)
  }

  const handleTestExtraction = () => {
    if (!emailData.subject || !emailData.sender) {
      toast({
        title: 'Subject and sender are required',
        status: 'warning',
        duration: 3000,
      })
      return
    }
    extractionMutation.mutate(emailData)
  }

  const handleTestBoth = () => {
    if (!emailData.subject || !emailData.sender) {
      toast({
        title: 'Subject and sender are required',
        status: 'warning',
        duration: 3000,
      })
      return
    }
    classificationMutation.mutate(emailData)
    extractionMutation.mutate(emailData)
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'green'
    if (confidence >= 0.6) return 'yellow'
    return 'red'
  }

  return (
    <Box>
      <Alert status="info" mb={6}>
        <AlertIcon />
        Test email classification and data extraction without saving to the database. Paste email content below and click test buttons.
      </Alert>

      <VStack spacing={6} align="stretch">
        {/* Email Input Form */}
        <Card>
          <CardHeader>
            <Heading size="md">Email Content</Heading>
          </CardHeader>
          <CardBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Subject</FormLabel>
                <Input
                  placeholder="Email subject line"
                  value={emailData.subject}
                  onChange={(e) => setEmailData({ ...emailData, subject: e.target.value })}
                />
              </FormControl>

              <HStack w="full" spacing={4}>
                <FormControl isRequired flex={1}>
                  <FormLabel>Sender Email</FormLabel>
                  <Input
                    placeholder="sender@example.com"
                    type="email"
                    value={emailData.sender}
                    onChange={(e) => setEmailData({ ...emailData, sender: e.target.value })}
                  />
                </FormControl>

                <FormControl flex={1}>
                  <FormLabel>Sender Name</FormLabel>
                  <Input
                    placeholder="Sender Display Name"
                    value={emailData.sender_name || ''}
                    onChange={(e) => setEmailData({ ...emailData, sender_name: e.target.value })}
                  />
                </FormControl>
              </HStack>

              <FormControl>
                <FormLabel>Email Body (Text)</FormLabel>
                <Textarea
                  placeholder="Paste email text content here..."
                  value={emailData.body_text || ''}
                  onChange={(e) => setEmailData({ ...emailData, body_text: e.target.value })}
                  rows={10}
                  fontFamily="monospace"
                  fontSize="sm"
                />
              </FormControl>

              <HStack spacing={4} w="full" justify="flex-end">
                <Button
                  colorScheme="blue"
                  onClick={handleTestClassification}
                  isLoading={classificationMutation.isPending}
                >
                  Test Classification
                </Button>
                <Button
                  colorScheme="purple"
                  onClick={handleTestExtraction}
                  isLoading={extractionMutation.isPending}
                >
                  Test Extraction
                </Button>
                <Button
                  colorScheme="green"
                  onClick={handleTestBoth}
                  isLoading={classificationMutation.isPending || extractionMutation.isPending}
                >
                  Test Both
                </Button>
              </HStack>
            </VStack>
          </CardBody>
        </Card>

        {/* Classification Results */}
        {classificationMutation.isPending && (
          <Card>
            <CardBody>
              <HStack>
                <Spinner size="sm" />
                <Text>Running classification test...</Text>
              </HStack>
            </CardBody>
          </Card>
        )}

        {classificationResult && (
          <Card>
            <CardHeader>
              <Heading size="md">Classification Results</Heading>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <HStack>
                  <Text fontWeight="bold">Is Subscription:</Text>
                  <Badge colorScheme={classificationResult.is_subscription ? 'green' : 'red'} fontSize="md">
                    {classificationResult.is_subscription ? 'YES' : 'NO'}
                  </Badge>
                </HStack>

                <HStack>
                  <Text fontWeight="bold">Confidence:</Text>
                  <Badge colorScheme={getConfidenceColor(classificationResult.confidence)} fontSize="md">
                    {(classificationResult.confidence * 100).toFixed(0)}%
                  </Badge>
                </HStack>

                <Box>
                  <Text fontWeight="bold" mb={2}>Category:</Text>
                  <Badge colorScheme="blue">{classificationResult.category}</Badge>
                </Box>

                <Divider />

                <Box>
                  <Text fontWeight="bold" mb={2}>AI Reasoning:</Text>
                  <Box bg="gray.50" p={4} borderRadius="md">
                    <Text whiteSpace="pre-wrap">{classificationResult.reasoning}</Text>
                  </Box>
                </Box>
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Extraction Results */}
        {extractionMutation.isPending && (
          <Card>
            <CardBody>
              <HStack>
                <Spinner size="sm" />
                <Text>Running extraction test...</Text>
              </HStack>
            </CardBody>
          </Card>
        )}

        {extractionResult && (
          <Card>
            <CardHeader>
              <Heading size="md">Extraction Results</Heading>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <HStack>
                  <Text fontWeight="bold">Confidence Score:</Text>
                  <Badge colorScheme={getConfidenceColor(extractionResult.confidence_score)} fontSize="md">
                    {(extractionResult.confidence_score * 100).toFixed(0)}%
                  </Badge>
                </HStack>

                <Divider />

                <VStack spacing={2} align="stretch">
                  <HStack>
                    <Text fontWeight="bold" minW="150px">Provider:</Text>
                    <Text>{extractionResult.provider || 'N/A'}</Text>
                  </HStack>

                  <HStack>
                    <Text fontWeight="bold" minW="150px">Amount:</Text>
                    <Text>{extractionResult.amount ? `${extractionResult.amount} ${extractionResult.currency}` : 'N/A'}</Text>
                  </HStack>

                  <HStack>
                    <Text fontWeight="bold" minW="150px">Billing Cycle:</Text>
                    <Text>{extractionResult.billing_cycle || 'N/A'}</Text>
                  </HStack>

                  <HStack>
                    <Text fontWeight="bold" minW="150px">Renewal Date:</Text>
                    <Text>{extractionResult.renewal_date || 'N/A'}</Text>
                  </HStack>

                  <HStack>
                    <Text fontWeight="bold" minW="150px">Custom Label:</Text>
                    <Text>{extractionResult.custom_label || 'N/A'}</Text>
                  </HStack>

                  <HStack>
                    <Text fontWeight="bold" minW="150px">Category:</Text>
                    <Badge colorScheme="blue">{extractionResult.category}</Badge>
                  </HStack>

                  <HStack>
                    <Text fontWeight="bold" minW="150px">Method:</Text>
                    <Text>{extractionResult.extraction_method}</Text>
                  </HStack>
                </VStack>

                {extractionResult.raw_response && (
                  <>
                    <Divider />
                    <Box>
                      <Text fontWeight="bold" mb={2}>Raw AI Response:</Text>
                      <Box bg="gray.50" p={4} borderRadius="md" maxH="300px" overflowY="auto">
                        <Code display="block" whiteSpace="pre-wrap" fontSize="xs">
                          {JSON.stringify(extractionResult.raw_response, null, 2)}
                        </Code>
                      </Box>
                    </Box>
                  </>
                )}
              </VStack>
            </CardBody>
          </Card>
        )}
      </VStack>
    </Box>
  )
}
