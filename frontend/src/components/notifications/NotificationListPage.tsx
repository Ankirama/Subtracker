import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Text,
  Button,
  Select,
  Card,
  CardBody,
  Icon,
  IconButton,
  Badge,
  useToast,
  Spinner,
  Center,
  Flex,
  ButtonGroup,
  useColorModeValue,
} from '@chakra-ui/react'
import {
  FiBell,
  FiCheck,
  FiX,
  FiSettings,
  FiFilter,
  FiChevronLeft,
  FiChevronRight,
} from 'react-icons/fi'
import { Link as RouterLink } from 'react-router-dom'
import { notificationsApi, NotificationType } from '../../api/notifications'
import { formatDistanceToNow } from '../../utils/timeFormat'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { SyncPreviewDrawer } from '../mailboxes/SyncPreviewDrawer'
import { NOTIFICATION_TYPE_ICONS } from '../../constants/enums'

const PAGE_SIZE = 20

type ReadFilter = '' | 'unread' | 'read'

const NOTIFICATION_TYPE_FILTER_OPTIONS: Array<{ value: NotificationType; label: string }> = [
  { value: 'TRIAL_ENDING', label: 'Trial Ending' },
  { value: 'RENEWAL_REMINDER', label: 'Renewal Reminder' },
  { value: 'WEEKLY_SUMMARY', label: 'Weekly Summary' },
  { value: 'MONTHLY_SUMMARY', label: 'Monthly Summary' },
  { value: 'INACTIVE_SUBSCRIPTION', label: 'Inactive Subscription' },
  { value: 'PRICE_CHANGE', label: 'Price Change' },
  { value: 'BUDGET_ALERT', label: 'Budget Alert' },
  { value: 'SYSTEM_ANNOUNCEMENT', label: 'System Announcement' },
  { value: 'SYNC_SKIPPED_MANY', label: 'Sync Skipped' },
  { value: 'SYNC_CIRCUIT_BREAKER', label: 'Sync Halted' },
  { value: 'SYNC_PREVIEW_AVAILABLE', label: 'Sync Preview' },
  { value: 'CANCELLATION_DETECTED', label: 'Cancellation Detected' },
]

const NOTIFICATION_TYPE_LABELS: Record<NotificationType, string> = {
  TRIAL_ENDING: 'Trial Ending',
  RENEWAL_REMINDER: 'Renewal Reminder',
  WEEKLY_SUMMARY: 'Weekly Summary',
  MONTHLY_SUMMARY: 'Monthly Summary',
  INACTIVE_SUBSCRIPTION: 'Inactive Subscription',
  PRICE_CHANGE: 'Price Change',
  BUDGET_ALERT: 'Budget Alert',
  SYSTEM_ANNOUNCEMENT: 'System Announcement',
  SYNC_SKIPPED_MANY: 'Sync Skipped',
  SYNC_CIRCUIT_BREAKER: 'Sync Halted',
  SYNC_PREVIEW_AVAILABLE: 'Sync preview',
  CANCELLATION_DETECTED: 'Cancellation Detected',
}

const getNotificationIcon = (type: string) =>
  (NOTIFICATION_TYPE_ICONS as Record<string, string>)[type] ?? '📬'

const getNotificationTypeLabel = (type: string) =>
  (NOTIFICATION_TYPE_LABELS as Record<string, string>)[type] ?? type

const getPriorityColor = (priority: string) => {
  switch (priority) {
    case 'high':
      return 'red'
    case 'medium':
      return 'orange'
    case 'low':
      return 'blue'
    default:
      return 'gray'
  }
}

export const NotificationListPage = () => {
  const [page, setPage] = useState(1)
  const [filterType, setFilterType] = useState<NotificationType | ''>('')
  const [filterRead, setFilterRead] = useState<ReadFilter>('')
  const [previewSyncId, setPreviewSyncId] = useState<string | null>(null)

  const toast = useToast()
  const queryClient = useQueryClient()

  const cardBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const hoverBg = useColorModeValue('gray.50', 'gray.700')
  const unreadBg = useColorModeValue('blue.50', 'blue.900')

  const queryKey = [
    'notifications',
    { page, filterType: filterType || null, filterRead: filterRead || null },
  ] as const

  const { data, isLoading, isError } = useQuery({
    queryKey,
    queryFn: () =>
      notificationsApi.getNotifications({
        page,
        page_size: PAGE_SIZE,
        unread_only: filterRead === 'unread' ? true : undefined,
        notification_type: filterType || undefined,
      }),
  })

  const notifications = data?.notifications ?? []
  const totalCount = data?.total ?? 0
  const unreadCount = data?.unread_count ?? 0
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  if (isError) {
    toast({
      id: 'notifications-load-error',
      title: 'Error',
      description: 'Failed to load notifications',
      status: 'error',
      duration: 3000,
    })
  }

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['notifications'] })

  const markAsReadMutation = useMutation({
    mutationFn: (notificationId: string) => notificationsApi.markAsRead([notificationId]),
    onSuccess: () => {
      invalidate()
    },
    onError: () => {
      toast({
        title: 'Error',
        description: 'Failed to mark notification as read',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const markAllAsReadMutation = useMutation({
    mutationFn: notificationsApi.markAllAsRead,
    onSuccess: () => {
      invalidate()
      toast({
        title: 'Success',
        description: 'All notifications marked as read',
        status: 'success',
        duration: 2000,
      })
    },
    onError: () => {
      toast({
        title: 'Error',
        description: 'Failed to mark all as read',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: notificationsApi.deleteNotification,
    onSuccess: () => {
      invalidate()
      toast({
        title: 'Success',
        description: 'Notification deleted',
        status: 'success',
        duration: 2000,
      })
    },
    onError: () => {
      toast({
        title: 'Error',
        description: 'Failed to delete notification',
        status: 'error',
        duration: 3000,
      })
    },
  })

  const resetFilters = () => {
    setFilterType('')
    setFilterRead('')
    setPage(1)
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack align="stretch" spacing={6}>
        {/* Header */}
        <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
          <Box>
            <HStack spacing={3} mb={2}>
              <Icon as={FiBell} boxSize={8} />
              <Heading size="lg">Notifications</Heading>
            </HStack>
            <Text color="text.subtle">
              {totalCount} total notifications • {unreadCount} unread
            </Text>
          </Box>
          <HStack spacing={2}>
            {unreadCount > 0 && (
              <Button
                leftIcon={<Icon as={FiCheck} />}
                colorScheme="blue"
                variant="outline"
                size="sm"
                onClick={() => markAllAsReadMutation.mutate()}
                isLoading={markAllAsReadMutation.isPending}
              >
                Mark all read
              </Button>
            )}
            <Button
              as={RouterLink}
              to="/notifications/settings"
              leftIcon={<Icon as={FiSettings} />}
              colorScheme="blue"
              variant="solid"
              size="sm"
            >
              Settings
            </Button>
          </HStack>
        </Flex>

        {/* Filters */}
        <Card bg={cardBg} borderColor={borderColor}>
          <CardBody>
            <HStack spacing={4} wrap="wrap">
              <HStack flex={1} minW="200px">
                <Icon as={FiFilter} color="gray.500" />
                <Select
                  placeholder="All types"
                  size="sm"
                  value={filterType}
                  onChange={(e) => {
                    setFilterType((e.target.value as NotificationType | '') || '')
                    setPage(1)
                  }}
                >
                  {NOTIFICATION_TYPE_FILTER_OPTIONS.map(({ value, label }) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
              </HStack>
              <HStack flex={1} minW="200px">
                <Select
                  placeholder="All notifications"
                  size="sm"
                  value={filterRead}
                  onChange={(e) => {
                    setFilterRead(e.target.value as ReadFilter)
                    setPage(1)
                  }}
                >
                  <option value="unread">Unread only</option>
                  <option value="read">Read only</option>
                </Select>
              </HStack>
              {(filterType || filterRead) && (
                <Button size="sm" variant="ghost" onClick={resetFilters}>
                  Clear filters
                </Button>
              )}
            </HStack>
          </CardBody>
        </Card>

        {/* Notifications List */}
        {isLoading ? (
          <Center py={20}>
            <Spinner size="xl" />
          </Center>
        ) : notifications.length === 0 ? (
          <Center py={20}>
            <VStack spacing={4}>
              <Text fontSize="6xl">🔕</Text>
              <Text fontSize="xl" fontWeight="medium" color="text.subtle">
                No notifications found
              </Text>
              <Text color="gray.500">
                {filterType || filterRead
                  ? 'Try adjusting your filters'
                  : 'You are all caught up'}
              </Text>
            </VStack>
          </Center>
        ) : (
          <VStack align="stretch" spacing={3}>
            {notifications.map((notification) => (
              <Card
                key={notification.id}
                bg={notification.is_read ? cardBg : unreadBg}
                borderColor={borderColor}
                _hover={{ bg: hoverBg }}
                cursor="pointer"
                onClick={() => {
                  if (!notification.is_read) {
                    markAsReadMutation.mutate(notification.id)
                  }
                  if (notification.type === 'SYNC_PREVIEW_AVAILABLE') {
                    const sid = (
                      notification.notification_metadata as
                        | Record<string, unknown>
                        | null
                    )?.['sync_history_id']
                    if (typeof sid === 'string') {
                      setPreviewSyncId(sid)
                    }
                  }
                }}
              >
                <CardBody>
                  <HStack align="start" spacing={4}>
                    {/* Icon */}
                    <Text fontSize="3xl">{getNotificationIcon(notification.type)}</Text>

                    {/* Content */}
                    <VStack align="start" flex={1} spacing={2}>
                      <HStack justify="space-between" w="full" wrap="wrap">
                        <HStack spacing={2}>
                          <Text
                            fontWeight={notification.is_read ? 'normal' : 'bold'}
                            fontSize="lg"
                          >
                            {notification.title}
                          </Text>
                          {!notification.is_read && (
                            <Badge colorScheme="blue" fontSize="xs">
                              NEW
                            </Badge>
                          )}
                        </HStack>
                        <HStack spacing={2}>
                          <Badge
                            colorScheme={getPriorityColor(notification.priority)}
                            fontSize="xs"
                          >
                            {notification.priority}
                          </Badge>
                          <Badge variant="subtle" fontSize="xs">
                            {getNotificationTypeLabel(notification.type)}
                          </Badge>
                        </HStack>
                      </HStack>

                      <MarkdownRenderer content={notification.message} color="gray.700" />

                      <HStack spacing={4} fontSize="sm" color="gray.500">
                        <Text>{formatDistanceToNow(new Date(notification.created_at))}</Text>
                        {notification.email_sent && <Text>📧 Email sent</Text>}
                      </HStack>
                    </VStack>

                    {/* Actions */}
                    <HStack spacing={1}>
                      {!notification.is_read && (
                        <IconButton
                          aria-label="Mark as read"
                          icon={<FiCheck />}
                          size="sm"
                          variant="ghost"
                          colorScheme="green"
                          onClick={(e) => {
                            e.stopPropagation()
                            markAsReadMutation.mutate(notification.id)
                          }}
                        />
                      )}
                      <IconButton
                        aria-label="Delete notification"
                        icon={<FiX />}
                        size="sm"
                        variant="ghost"
                        colorScheme="red"
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteMutation.mutate(notification.id)
                        }}
                      />
                    </HStack>
                  </HStack>
                </CardBody>
              </Card>
            ))}
          </VStack>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <Card bg={cardBg} borderColor={borderColor}>
            <CardBody>
              <Flex justify="space-between" align="center">
                <Text fontSize="sm" color="text.subtle">
                  Page {page} of {totalPages}
                </Text>
                <ButtonGroup size="sm" isAttached variant="outline">
                  <IconButton
                    aria-label="Previous page"
                    icon={<FiChevronLeft />}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    isDisabled={page === 1}
                  />
                  <IconButton
                    aria-label="Next page"
                    icon={<FiChevronRight />}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    isDisabled={page === totalPages}
                  />
                </ButtonGroup>
              </Flex>
            </CardBody>
          </Card>
        )}
      </VStack>

      {/* Sync Preview Drawer */}
      <SyncPreviewDrawer
        syncHistoryId={previewSyncId}
        isOpen={!!previewSyncId}
        onClose={() => setPreviewSyncId(null)}
      />
    </Container>
  )
}
