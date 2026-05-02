import {
  Badge,
  Box,
  Button,
  Code,
  Divider,
  HStack,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Text,
  VStack,
} from '@chakra-ui/react'
import { FiPlus, FiX } from 'react-icons/fi'
import DOMPurify from 'dompurify'

import type { EmailDetailResponse } from '../../types'

interface EmailDetailModalProps {
  email: EmailDetailResponse | null
  isOpen: boolean
  onClose: () => void
  onMarkNotSubscription: () => void
  onCreateSubscription: () => void
  isMarkPending: boolean
}

const confidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return 'green'
  if (confidence >= 0.6) return 'yellow'
  return 'red'
}

export const EmailDetailModal = ({
  email,
  isOpen,
  onClose,
  onMarkNotSubscription,
  onCreateSubscription,
  isMarkPending,
}: EmailDetailModalProps) => {
  return (
    <Modal isOpen={isOpen} onClose={onClose} size="4xl" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Email Details</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          {email && (
            <VStack spacing={4} align="stretch">
              <Box>
                <Text fontWeight="bold" mb={2}>Subject:</Text>
                <Text>{email.subject}</Text>
              </Box>

              <HStack spacing={4}>
                <Box flex={1}>
                  <Text fontWeight="bold" mb={2}>From:</Text>
                  <Text>{email.sender_name || 'Unknown'}</Text>
                  <Text fontSize="sm" color="gray.500">{email.sender}</Text>
                </Box>
                <Box flex={1}>
                  <Text fontWeight="bold" mb={2}>To:</Text>
                  <Text fontSize="sm">{email.recipient}</Text>
                </Box>
              </HStack>

              <HStack spacing={4}>
                <Box>
                  <Text fontWeight="bold" mb={2}>Date:</Text>
                  <Text>{new Date(email.date).toLocaleString()}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold" mb={2}>Confidence:</Text>
                  <Badge colorScheme={confidenceColor(email.classification_confidence)}>
                    {(email.classification_confidence * 100).toFixed(0)}%
                  </Badge>
                </Box>
                <Box>
                  <Text fontWeight="bold" mb={2}>Subscription Status:</Text>
                  <Badge colorScheme={email.has_linked_subscription ? 'green' : 'orange'}>
                    {email.has_linked_subscription ? 'Linked' : 'No Subscription'}
                  </Badge>
                </Box>
              </HStack>

              <Divider />

              <Box>
                <Text fontWeight="bold" mb={2}>Email Body:</Text>
                <Tabs colorScheme="blue" variant="enclosed">
                  <TabList>
                    <Tab>Source Code</Tab>
                    {email.body_html && <Tab>Rendered HTML</Tab>}
                  </TabList>
                  <TabPanels>
                    <TabPanel p={0} pt={4}>
                      <Box bg="bg.subtle" p={4} borderRadius="md" maxH="400px" overflowY="auto">
                        <Text whiteSpace="pre-wrap" fontFamily="monospace" fontSize="sm">
                          {email.body_html || email.body_text || 'No content'}
                        </Text>
                      </Box>
                    </TabPanel>
                    {email.body_html && (
                      <TabPanel p={0} pt={4}>
                        <SanitizedHtmlPreview html={email.body_html} />
                      </TabPanel>
                    )}
                  </TabPanels>
                </Tabs>
              </Box>

              {email.classification_reasoning && (
                <Box>
                  <Text fontWeight="bold" mb={2}>Classification Reasoning:</Text>
                  <Box bg="bg.subtle" p={4} borderRadius="md" maxH="200px" overflowY="auto">
                    <Code display="block" whiteSpace="pre-wrap" fontSize="xs">
                      {JSON.stringify(email.classification_reasoning, null, 2)}
                    </Code>
                  </Box>
                </Box>
              )}
            </VStack>
          )}
        </ModalBody>
        <ModalFooter>
          <HStack spacing={3} flex={1} justify="space-between">
            <Box>
              {email && email.is_subscription && (
                <Button
                  colorScheme="red"
                  variant="outline"
                  leftIcon={<FiX />}
                  onClick={onMarkNotSubscription}
                  isLoading={isMarkPending}
                >
                  Not a Subscription
                </Button>
              )}
            </Box>
            <HStack spacing={3}>
              {email && !email.has_linked_subscription && (
                <Button colorScheme="green" leftIcon={<FiPlus />} onClick={onCreateSubscription}>
                  Create Subscription
                </Button>
              )}
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
            </HStack>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}

const SanitizedHtmlPreview = ({ html }: { html: string }) => {
  const sanitized = DOMPurify.sanitize(html)
  return (
    <Box
      bg="white"
      p={4}
      borderRadius="md"
      border="1px solid"
      borderColor="gray.200"
      maxH="400px"
      overflowY="auto"
      dangerouslySetInnerHTML={{ __html: sanitized }}
    />
  )
}
