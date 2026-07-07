import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  HStack,
  Card,
  CardBody,
  Badge,
  Button,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  useDisclosure,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Icon,
} from '@chakra-ui/react'
import { FiAlertTriangle, FiCheck, FiGitMerge } from 'react-icons/fi'
import { ProviderLogo } from '../common/ProviderLogo'
import { subscriptionsAPI } from '../../api/subscriptions'

interface Subscription {
  id: string
  provider: string
  amount: number | null
  currency: string
  billing_cycle: string
  custom_label: string | null
  created_at: string
  renewal_date: string | null
  is_active: boolean
  email_count: number
}

interface DuplicateGroup {
  provider: string
  billing_cycle: string
  count: number
  similar_amounts: boolean
  subscriptions: Subscription[]
}

export default function DuplicatesPage() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const { isOpen, onOpen, onClose } = useDisclosure()
  const [selectedGroup, setSelectedGroup] = useState<DuplicateGroup | null>(null)
  const [targetId, setTargetId] = useState<string>('')

  // Fetch duplicate groups
  const { data: duplicateGroups, isLoading, error } = useQuery<DuplicateGroup[]>({
    queryKey: ['duplicates'],
    queryFn: () => subscriptionsAPI.getDuplicates()
  })

  // Every subscription in the selected group except the chosen target.
  const sourceIds =
    selectedGroup?.subscriptions
      .map((sub) => sub.id)
      .filter((id) => id !== targetId) ?? []

  // Merge mutation: merge the whole group into a single target in one call.
  const mergeMutation = useMutation({
    mutationFn: ({ targetId, sourceIds }: { targetId: string; sourceIds: string[] }) =>
      subscriptionsAPI.mergeGroup(targetId, sourceIds),
    onSuccess: (data) => {
      toast({
        title: 'Merge Successful',
        description: data.message,
        status: 'success',
        duration: 5000,
        isClosable: true,
      })
      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ['duplicates'] })
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      onClose()
    },
    onError: (error: any) => {
      toast({
        title: 'Merge Failed',
        description: error.response?.data?.detail || 'Failed to merge subscriptions',
        status: 'error',
        duration: 5000,
        isClosable: true,
      })
    }
  })

  const handleMergeClick = (group: DuplicateGroup) => {
    setSelectedGroup(group)
    // Pre-select the oldest subscription as the target to keep.
    const sorted = [...group.subscriptions].sort((a, b) =>
      new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    )
    setTargetId(sorted[0].id) // Oldest
    onOpen()
  }

  const handleMerge = () => {
    if (targetId && sourceIds.length > 0) {
      mergeMutation.mutate({ targetId, sourceIds })
    }
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A'
    return new Date(dateStr).toLocaleDateString()
  }

  const formatAmount = (amount: number | null, currency: string) => {
    if (amount === null) return 'N/A'
    return `${currency || 'EUR'} ${amount.toFixed(2)}`
  }

  if (isLoading) {
    return (
      <Container maxW="container.xl" py={8}>
        <VStack spacing={4}>
          <Spinner size="xl" />
          <Text>Loading duplicates...</Text>
        </VStack>
      </Container>
    )
  }

  if (error) {
    return (
      <Container maxW="container.xl" py={8}>
        <Alert status="error">
          <AlertIcon />
          <AlertTitle>Error loading duplicates</AlertTitle>
          <AlertDescription>{(error as Error).message}</AlertDescription>
        </Alert>
      </Container>
    )
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack align="stretch" spacing={6}>
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>Duplicate Subscriptions</Heading>
          <Text color="text.subtle">
            Review and merge duplicate subscriptions to keep your data clean.
          </Text>
        </Box>

        {/* No duplicates found */}
        {!duplicateGroups || duplicateGroups.length === 0 ? (
          <Alert status="success" borderRadius="md">
            <AlertIcon as={FiCheck} />
            <Box>
              <AlertTitle>No Duplicates Found</AlertTitle>
              <AlertDescription>
                All your subscriptions appear to be unique. Great job keeping your data clean!
              </AlertDescription>
            </Box>
          </Alert>
        ) : (
          /* Duplicate groups */
          <VStack align="stretch" spacing={4}>
            {duplicateGroups.map((group, idx) => (
              <Card key={idx} variant="outline">
                <CardBody>
                  <VStack align="stretch" spacing={4}>
                    {/* Group Header */}
                    <HStack justify="space-between">
                      <HStack spacing={3}>
                        <ProviderLogo providerName={group.provider} size="md" />
                        <Box>
                          <HStack>
                            <Heading size="md">{group.provider}</Heading>
                            <Badge colorScheme="red">
                              <Icon as={FiAlertTriangle} mr={1} />
                              {group.count} duplicates
                            </Badge>
                            {group.similar_amounts && (
                              <Badge colorScheme="orange">Similar amounts</Badge>
                            )}
                          </HStack>
                          <Text fontSize="sm" color="text.subtle">
                            {group.billing_cycle || 'Unknown'} billing
                          </Text>
                        </Box>
                      </HStack>
                      <Button
                        leftIcon={<FiGitMerge />}
                        colorScheme="blue"
                        size="sm"
                        onClick={() => handleMergeClick(group)}
                      >
                        Merge Duplicates
                      </Button>
                    </HStack>

                    {/* Subscriptions Table */}
                    <Table size="sm" variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Created</Th>
                          <Th>Amount</Th>
                          <Th>Label</Th>
                          <Th>Emails</Th>
                          <Th>Status</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {group.subscriptions.map((sub) => (
                          <Tr key={sub.id}>
                            <Td>{formatDate(sub.created_at)}</Td>
                            <Td fontWeight="bold">{formatAmount(sub.amount, sub.currency)}</Td>
                            <Td>{sub.custom_label || '-'}</Td>
                            <Td>{sub.email_count} emails</Td>
                            <Td>
                              <Badge colorScheme={sub.is_active ? 'green' : 'gray'}>
                                {sub.is_active ? 'Active' : 'Inactive'}
                              </Badge>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </VStack>
                </CardBody>
              </Card>
            ))}
          </VStack>
        )}
      </VStack>

      {/* Merge Confirmation Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Merge Duplicate Subscriptions</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedGroup && (
              <VStack align="stretch" spacing={4}>
                <Alert status="info">
                  <AlertIcon />
                  <Box>
                    <AlertTitle>About Merging</AlertTitle>
                    <AlertDescription fontSize="sm">
                      The subscription you select as the target will be kept. All other duplicates in
                      this group will be merged into it — their emails are transferred to the target
                      and the source subscriptions are deleted.
                    </AlertDescription>
                  </Box>
                </Alert>

                <Box>
                  <Text fontWeight="bold" mb={2}>Select the subscription to keep:</Text>
                  <VStack align="stretch" spacing={2}>
                    {selectedGroup.subscriptions.map((sub) => (
                      <HStack
                        key={sub.id}
                        p={3}
                        borderWidth="1px"
                        borderRadius="md"
                        bg={targetId === sub.id ? 'blue.50' : 'white'}
                        cursor="pointer"
                        onClick={() => setTargetId(sub.id)}
                      >
                        <ProviderLogo providerName={sub.provider} size="sm" />
                        <Box flex={1}>
                          <HStack>
                            <Text fontWeight="medium">{formatAmount(sub.amount, sub.currency)}</Text>
                            {sub.custom_label && (
                              <Text fontSize="sm" color="text.subtle">({sub.custom_label})</Text>
                            )}
                          </HStack>
                          <Text fontSize="xs" color="gray.500">
                            Created {formatDate(sub.created_at)} • {sub.email_count} emails
                          </Text>
                        </Box>
                        {targetId === sub.id ? (
                          <Badge colorScheme="blue">Target (Keep)</Badge>
                        ) : (
                          <Badge colorScheme="gray">Will be merged</Badge>
                        )}
                      </HStack>
                    ))}
                  </VStack>
                </Box>

                {targetId && sourceIds.length > 0 && (
                  <Alert status="warning">
                    <AlertIcon />
                    <Box fontSize="sm">
                      <AlertTitle>Confirm Merge</AlertTitle>
                      <AlertDescription>
                        This will merge {sourceIds.length}{' '}
                        {sourceIds.length === 1 ? 'subscription' : 'subscriptions'} into the target
                        and delete {sourceIds.length === 1 ? 'it' : 'them'}. This cannot be undone.
                        All data will be preserved in the target subscription.
                      </AlertDescription>
                    </Box>
                  </Alert>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={handleMerge}
              isLoading={mergeMutation.isPending}
              isDisabled={!targetId || sourceIds.length === 0}
            >
              Merge Subscriptions
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Container>
  )
}
