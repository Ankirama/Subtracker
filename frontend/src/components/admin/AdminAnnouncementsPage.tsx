import { useState } from 'react'
import {
  Box,
  Button,
  Heading,
  VStack,
  HStack,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  Select,
  Radio,
  RadioGroup,
  Stack,
  useToast,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Card,
  CardBody,
  Text,
  Badge,
  useColorModeValue,
  Divider,
  Code,
  UnorderedList,
  ListItem,
  Collapse,
  IconButton,
} from '@chakra-ui/react'
import { FiBell, FiSend, FiHelpCircle } from 'react-icons/fi'
import {
  adminApi,
  type SystemAnnouncementCreate,
  type SystemAnnouncementResponse,
} from '../../api/admin'
import { MarkdownRenderer } from '../common/MarkdownRenderer'

const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Low', color: 'blue', description: 'General information' },
  { value: 'medium', label: 'Medium', color: 'orange', description: 'Important updates' },
  { value: 'high', label: 'High', color: 'red', description: 'Critical announcements' },
]

export const AdminAnnouncementsPage = () => {
  const [formData, setFormData] = useState<SystemAnnouncementCreate>({
    title: '',
    message: '',
    priority: 'medium',
    target_all_users: true,
    target_user_ids: [],
  })

  const [isSending, setIsSending] = useState(false)
  const [lastResponse, setLastResponse] = useState<SystemAnnouncementResponse | null>(null)
  const [showMarkdownHelp, setShowMarkdownHelp] = useState(false)

  const toast = useToast()
  const bgColor = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')

  const handleSubmit = async () => {
    if (!formData.title.trim() || !formData.message.trim()) {
      toast({
        title: 'Validation Error',
        description: 'Title and message are required',
        status: 'error',
        duration: 3000,
      })
      return
    }

    try {
      setIsSending(true)
      const response = await adminApi.broadcastAnnouncement(formData)
      setLastResponse(response)

      toast({
        title: 'Announcement Broadcast Started',
        description: response.message,
        status: 'success',
        duration: 5000,
      })

      // Reset form
      setFormData({
        title: '',
        message: '',
        priority: 'medium',
        target_all_users: true,
        target_user_ids: [],
      })
    } catch (error) {
      toast({
        title: 'Error Broadcasting Announcement',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      })
    } finally {
      setIsSending(false)
    }
  }

  const currentPriorityInfo = PRIORITY_OPTIONS.find((p) => p.value === formData.priority)

  return (
    <Box>
      <VStack align="stretch" spacing={6}>
        {/* Header */}
        <HStack>
          <FiBell size={28} />
          <Heading size="lg">System Announcements</Heading>
        </HStack>

        <Alert status="warning">
          <AlertIcon />
          <Box>
            <AlertTitle>Broadcast to Users</AlertTitle>
            <AlertDescription>
              Send system-wide announcements to all users. Messages will be delivered as in-app notifications
              and emails based on user preferences.
            </AlertDescription>
          </Box>
        </Alert>

        {/* Last Broadcast Result */}
        {lastResponse && (
          <Alert status="success" variant="left-accent">
            <AlertIcon />
            <Box flex="1">
              <AlertTitle>Last Broadcast Successful</AlertTitle>
              <AlertDescription>
                <VStack align="start" spacing={1} fontSize="sm">
                  <Text>Announcement ID: {lastResponse.announcement_id}</Text>
                  <Text>Notifications Created: {lastResponse.notifications_created}</Text>
                  <Text>Emails Sent: {lastResponse.emails_sent}</Text>
                </VStack>
              </AlertDescription>
            </Box>
          </Alert>
        )}

        {/* Announcement Form */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth="1px">
          <CardBody>
            <VStack spacing={6} align="stretch">
              <FormControl isRequired>
                <FormLabel>Announcement Title</FormLabel>
                <Input
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  placeholder="e.g., Scheduled Maintenance, New Feature Release"
                  size="lg"
                />
              </FormControl>

              <FormControl isRequired>
                <HStack justify="space-between" mb={2}>
                  <FormLabel mb={0}>Message (Markdown supported)</FormLabel>
                  <IconButton
                    aria-label="Toggle markdown help"
                    icon={<FiHelpCircle />}
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowMarkdownHelp(!showMarkdownHelp)}
                  />
                </HStack>
                <Collapse in={showMarkdownHelp} animateOpacity>
                  <Box
                    bg="bg.accent.blue"
                    borderColor="blue.200"
                    borderWidth="1px"
                    borderRadius="md"
                    p={4}
                    mb={3}
                  >
                    <Text fontWeight="bold" fontSize="sm" mb={2}>
                      📝 Markdown Quick Reference:
                    </Text>
                    <UnorderedList fontSize="sm" spacing={1}>
                      <ListItem>
                        <Code>**bold**</Code> → <strong>bold</strong>
                      </ListItem>
                      <ListItem>
                        <Code>*italic*</Code> → <em>italic</em>
                      </ListItem>
                      <ListItem>
                        <Code>[link](url)</Code> → creates a link
                      </ListItem>
                      <ListItem>
                        <Code>- item</Code> → bullet list
                      </ListItem>
                      <ListItem>
                        <Code>1. item</Code> → numbered list
                      </ListItem>
                      <ListItem>
                        <Code>## Heading</Code> → heading
                      </ListItem>
                      <ListItem>
                        <Code>`code`</Code> → inline code
                      </ListItem>
                    </UnorderedList>
                  </Box>
                </Collapse>
                <Textarea
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  placeholder="Enter your announcement message here...

Example with markdown:
**Important:** System maintenance scheduled for tonight.

We'll be performing:
- Database upgrades
- Security patches
- Performance improvements

Expected downtime: ~30 minutes

[View Schedule](https://example.com/schedule)"
                  rows={12}
                  resize="vertical"
                  fontFamily="monospace"
                  fontSize="sm"
                />
                <Text fontSize="sm" color="gray.500" mt={2}>
                  {formData.message.length} characters • Markdown formatting supported
                </Text>
              </FormControl>

              <FormControl>
                <FormLabel>Priority</FormLabel>
                <Select
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value as any })}
                >
                  {PRIORITY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label} - {option.description}
                    </option>
                  ))}
                </Select>
                {currentPriorityInfo && (
                  <HStack mt={2}>
                    <Badge colorScheme={currentPriorityInfo.color} fontSize="sm">
                      {currentPriorityInfo.label} Priority
                    </Badge>
                    <Text fontSize="sm" color="text.subtle">
                      {currentPriorityInfo.description}
                    </Text>
                  </HStack>
                )}
              </FormControl>

              <Divider />

              <FormControl>
                <FormLabel>Target Audience</FormLabel>
                <RadioGroup
                  value={formData.target_all_users ? 'all' : 'specific'}
                  onChange={(value) =>
                    setFormData({ ...formData, target_all_users: value === 'all' })
                  }
                >
                  <Stack direction="column" spacing={3}>
                    <Radio value="all">
                      <Text fontWeight="medium">All Users</Text>
                      <Text fontSize="sm" color="text.subtle">
                        Send to all active users in the system
                      </Text>
                    </Radio>
                    <Radio value="specific" isDisabled>
                      <Text fontWeight="medium">Specific Users</Text>
                      <Text fontSize="sm" color="text.subtle">
                        Target specific users (coming soon)
                      </Text>
                    </Radio>
                  </Stack>
                </RadioGroup>
              </FormControl>

              {/* Preview Section */}
              <Box borderWidth="1px" borderColor={borderColor} borderRadius="md" p={4} bg="bg.subtle">
                <Text fontSize="sm" fontWeight="bold" mb={3} color="gray.700">
                  📱 Preview (as users will see it)
                </Text>
                {formData.title && (
                  <>
                    <HStack mb={3}>
                      <Text fontSize="lg" fontWeight="bold">
                        📢 {formData.title}
                      </Text>
                      <Badge colorScheme={currentPriorityInfo?.color}>
                        {currentPriorityInfo?.label}
                      </Badge>
                    </HStack>
                    {formData.message ? (
                      <MarkdownRenderer content={formData.message} />
                    ) : (
                      <Text color="gray.500" fontSize="sm">
                        (No message yet)
                      </Text>
                    )}
                  </>
                )}
                {!formData.title && (
                  <Text color="gray.500" fontSize="sm">
                    Fill in the title and message to see a preview
                  </Text>
                )}
              </Box>
            </VStack>
          </CardBody>
        </Card>

        {/* Action Buttons */}
        <HStack justify="flex-end">
          <Button
            size="lg"
            colorScheme="blue"
            leftIcon={<FiSend />}
            onClick={handleSubmit}
            isLoading={isSending}
            loadingText="Broadcasting..."
            isDisabled={!formData.title.trim() || !formData.message.trim()}
          >
            Broadcast Announcement
          </Button>
        </HStack>

        {/* Info Section */}
        <Card bg="bg.accent.blue" borderColor="blue.200" borderWidth="1px">
          <CardBody>
            <VStack align="start" spacing={2}>
              <Text fontWeight="bold" color="blue.800">
                💡 How it works
              </Text>
              <Text fontSize="sm" color="blue.700">
                • Announcements are sent asynchronously via background tasks
              </Text>
              <Text fontSize="sm" color="blue.700">
                • Users receive in-app notifications immediately
              </Text>
              <Text fontSize="sm" color="blue.700">
                • Email delivery respects user notification preferences
              </Text>
              <Text fontSize="sm" color="blue.700">
                • High priority announcements use red styling, low priority uses blue
              </Text>
            </VStack>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  )
}
