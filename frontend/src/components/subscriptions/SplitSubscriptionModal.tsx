import { useState } from 'react'
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Button,
  VStack,
  HStack,
  Text,
  Checkbox,
  Input,
  FormControl,
  FormLabel,
  Alert,
  AlertIcon,
  Box,
  Badge,
  Divider,
  Icon,
  useToast,
} from '@chakra-ui/react'
import { FiMail, FiScissors } from 'react-icons/fi'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { subscriptionsAPI } from '../../api/subscriptions'
import { SubscriptionDetail } from '../../types'

interface SplitSubscriptionModalProps {
  isOpen: boolean
  onClose: () => void
  subscription: SubscriptionDetail
}

interface EmailGroup {
  email_ids: string[]
  custom_label: string
  amount: string
}

export const SplitSubscriptionModal = ({
  isOpen,
  onClose,
  subscription,
}: SplitSubscriptionModalProps) => {
  const toast = useToast()
  const queryClient = useQueryClient()

  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set())
  const [groups, setGroups] = useState<EmailGroup[]>([
    { email_ids: [], custom_label: '', amount: '' },
    { email_ids: [], custom_label: '', amount: '' },
  ])

  const splitMutation = useMutation({
    mutationFn: async (emailGroups: any[]) => {
      return subscriptionsAPI.split(subscription.id, emailGroups)
    },
    onSuccess: (data) => {
      toast({
        title: 'Subscription split successfully',
        description: data.message,
        status: 'success',
        duration: 5000,
        isClosable: true,
      })
      queryClient.invalidateQueries({ queryKey: ['subscription', subscription.id] })
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      onClose()
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to split subscription',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 7000,
        isClosable: true,
      })
    },
  })

  const toggleEmail = (emailId: string) => {
    const newSelected = new Set(selectedEmails)
    if (newSelected.has(emailId)) {
      newSelected.delete(emailId)
    } else {
      newSelected.add(emailId)
    }
    setSelectedEmails(newSelected)
  }

  const assignToGroup = (groupIndex: number, emailIds: string[]) => {
    const newGroups = [...groups]
    newGroups[groupIndex].email_ids = emailIds
    setGroups(newGroups)
  }

  const updateGroupLabel = (groupIndex: number, label: string) => {
    const newGroups = [...groups]
    newGroups[groupIndex].custom_label = label
    setGroups(newGroups)
  }

  const updateGroupAmount = (groupIndex: number, amount: string) => {
    const newGroups = [...groups]
    newGroups[groupIndex].amount = amount
    setGroups(newGroups)
  }

  const addGroup = () => {
    setGroups([...groups, { email_ids: [], custom_label: '', amount: '' }])
  }

  const removeGroup = (index: number) => {
    if (groups.length <= 2) {
      toast({
        title: 'Cannot remove group',
        description: 'Must have at least 2 groups for splitting',
        status: 'warning',
        duration: 3000,
      })
      return
    }
    setGroups(groups.filter((_, i) => i !== index))
  }

  const handleSplit = () => {
    // Validate all emails are assigned
    const allAssignedEmails = new Set<string>()
    groups.forEach(g => g.email_ids.forEach(id => allAssignedEmails.add(id)))

    const totalEmails = subscription.source_emails?.length || 0
    if (allAssignedEmails.size !== totalEmails) {
      toast({
        title: 'Incomplete assignment',
        description: 'All emails must be assigned to a group',
        status: 'error',
        duration: 5000,
      })
      return
    }

    // Validate each group has at least one email
    if (groups.some(g => g.email_ids.length === 0)) {
      toast({
        title: 'Empty group',
        description: 'Each group must have at least one email',
        status: 'error',
        duration: 5000,
      })
      return
    }

    // Prepare API payload
    const emailGroups = groups.map(g => ({
      email_ids: g.email_ids,
      custom_label: g.custom_label || undefined,
      amount: g.amount ? parseFloat(g.amount) : undefined,
    }))

    splitMutation.mutate(emailGroups)
  }

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="4xl" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>
          <HStack>
            <Icon as={FiScissors} />
            <Text>Split Subscription</Text>
          </HStack>
        </ModalHeader>
        <ModalCloseButton />

        <ModalBody>
          <VStack align="stretch" spacing={6}>
            <Alert status="info">
              <AlertIcon />
              <Text fontSize="sm">
                Assign each email to a group. Each group will become a separate subscription.
              </Text>
            </Alert>

            {/* Groups */}
            {groups.map((group, groupIndex) => (
              <Box key={groupIndex} p={4} border="2px" borderColor="gray.200" borderRadius="md">
                <VStack align="stretch" spacing={3}>
                  <HStack justify="space-between">
                    <Text fontWeight="bold" fontSize="lg">
                      Group {groupIndex + 1}
                    </Text>
                    <HStack>
                      <Badge colorScheme="blue">{group.email_ids.length} emails</Badge>
                      {groups.length > 2 && (
                        <Button
                          size="xs"
                          colorScheme="red"
                          variant="ghost"
                          onClick={() => removeGroup(groupIndex)}
                        >
                          Remove
                        </Button>
                      )}
                    </HStack>
                  </HStack>

                  <HStack>
                    <FormControl>
                      <FormLabel fontSize="sm">Custom Label</FormLabel>
                      <Input
                        size="sm"
                        placeholder={`${subscription.provider} Service ${groupIndex + 1}`}
                        value={group.custom_label}
                        onChange={(e) => updateGroupLabel(groupIndex, e.target.value)}
                      />
                    </FormControl>
                    <FormControl>
                      <FormLabel fontSize="sm">Amount</FormLabel>
                      <Input
                        size="sm"
                        type="number"
                        step="0.01"
                        placeholder="Optional"
                        value={group.amount}
                        onChange={(e) => updateGroupAmount(groupIndex, e.target.value)}
                      />
                    </FormControl>
                  </HStack>

                  {/* Email selection for this group */}
                  <Box>
                    <Text fontSize="sm" fontWeight="semibold" mb={2}>
                      Select emails for this group:
                    </Text>
                    <VStack align="stretch" spacing={2} maxH="200px" overflowY="auto">
                      {subscription.source_emails?.map((link) => {
                        const isInThisGroup = group.email_ids.includes(link.email.id)
                        const isInOtherGroup = groups.some(
                          (g, i) => i !== groupIndex && g.email_ids.includes(link.email.id)
                        )

                        return (
                          <Box
                            key={link.email.id}
                            p={2}
                            bg={isInThisGroup ? 'blue.50' : 'white'}
                            border="1px"
                            borderColor={isInThisGroup ? 'blue.200' : 'gray.200'}
                            borderRadius="md"
                          >
                            <Checkbox
                              isChecked={isInThisGroup}
                              isDisabled={isInOtherGroup}
                              onChange={() => {
                                const newGroup = [...groups]
                                if (isInThisGroup) {
                                  newGroup[groupIndex].email_ids = newGroup[groupIndex].email_ids.filter(
                                    id => id !== link.email.id
                                  )
                                } else {
                                  newGroup[groupIndex].email_ids.push(link.email.id)
                                }
                                setGroups(newGroup)
                              }}
                            >
                              <VStack align="start" spacing={0}>
                                <HStack>
                                  <Icon as={FiMail} color="blue.500" boxSize={3} />
                                  <Text fontSize="sm" fontWeight="semibold">
                                    {link.email.subject}
                                  </Text>
                                </HStack>
                                <Text fontSize="xs" color="gray.600">
                                  {formatDateTime(link.email.date)}
                                  {link.extraction_role && (
                                    <Badge ml={2} fontSize="xs" colorScheme="purple">
                                      {link.extraction_role}
                                    </Badge>
                                  )}
                                </Text>
                              </VStack>
                            </Checkbox>
                          </Box>
                        )
                      })}
                    </VStack>
                  </Box>
                </VStack>
              </Box>
            ))}

            <Button
              variant="outline"
              colorScheme="blue"
              size="sm"
              onClick={addGroup}
            >
              + Add Another Group
            </Button>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <HStack spacing={3}>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={handleSplit}
              isLoading={splitMutation.isPending}
              loadingText="Splitting..."
            >
              Split Subscription
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}
