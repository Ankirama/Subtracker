import { useState, useEffect } from 'react'
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
  Divider,
  useToast,
  Spinner,
  Center,
  Flex,
  ButtonGroup,
  useColorModeValue,
} from '@chakra-ui/react'
import { FiBell, FiCheck, FiX, FiSettings, FiFilter, FiChevronLeft, FiChevronRight } from 'react-icons/fi'
import { Link as RouterLink } from 'react-router-dom'
import { notificationsApi, Notification } from '../../api/notifications'
import { formatDistanceToNow } from '../../utils/timeFormat'
import { MarkdownRenderer } from '../common/MarkdownRenderer'

export const NotificationListPage = () => {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [unreadCount, setUnreadCount] = useState(0)
  const [filterType, setFilterType] = useState<string>('')
  const [filterRead, setFilterRead] = useState<string>('')
  const toast = useToast()

  const cardBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const hoverBg = useColorModeValue('gray.50', 'gray.700')
  const unreadBg = useColorModeValue('blue.50', 'blue.900')

  const pageSize = 20

  useEffect(() => {
    fetchNotifications()
  }, [page, filterType, filterRead])

  const fetchNotifications = async () => {
    setIsLoading(true)
    try {
      const params: any = {
        page,
        page_size: pageSize,
      }

      if (filterRead === 'unread') {
        params.unread_only = true
      }

      if (filterType) {
        params.notification_type = filterType
      }

      const data = await notificationsApi.getNotifications(params)
      setNotifications(data.notifications)
      setTotalCount(data.total)
      setUnreadCount(data.unread_count)
      setTotalPages(Math.ceil(data.total / pageSize))
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load notifications',
        status: 'error',
        duration: 3000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleMarkAsRead = async (notificationId: string) => {
    try {
      await notificationsApi.markAsRead([notificationId])
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
      )
      setUnreadCount((prev) => Math.max(0, prev - 1))
      toast({
        title: 'Success',
        description: 'Notification marked as read',
        status: 'success',
        duration: 2000,
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to mark notification as read',
        status: 'error',
        duration: 3000,
      })
    }
  }

  const handleMarkAllAsRead = async () => {
    try {
      await notificationsApi.markAllAsRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
      setUnreadCount(0)
      toast({
        title: 'Success',
        description: 'All notifications marked as read',
        status: 'success',
        duration: 2000,
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to mark all as read',
        status: 'error',
        duration: 3000,
      })
    }
  }

  const handleDelete = async (notificationId: string) => {
    const notification = notifications.find((n) => n.id === notificationId)
    try {
      await notificationsApi.deleteNotification(notificationId)
      setNotifications((prev) => prev.filter((n) => n.id !== notificationId))
      setTotalCount((prev) => prev - 1)
      if (notification && !notification.is_read) {
        setUnreadCount((prev) => Math.max(0, prev - 1))
      }
      toast({
        title: 'Success',
        description: 'Notification deleted',
        status: 'success',
        duration: 2000,
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to delete notification',
        status: 'error',
        duration: 3000,
      })
    }
  }

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

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'trial_ending':
        return '⚠️'
      case 'renewal_reminder':
        return '🔔'
      case 'weekly_summary':
        return '📊'
      case 'monthly_summary':
        return '📈'
      case 'inactive_subscription':
        return '⏸️'
      case 'price_change':
        return '💰'
      case 'system_announcement':
        return '📢'
      default:
        return '📬'
    }
  }

  const getNotificationTypeLabel = (type: string) => {
    switch (type) {
      case 'trial_ending':
        return 'Trial Ending'
      case 'renewal_reminder':
        return 'Renewal Reminder'
      case 'weekly_summary':
        return 'Weekly Summary'
      case 'monthly_summary':
        return 'Monthly Summary'
      case 'inactive_subscription':
        return 'Inactive Subscription'
      case 'price_change':
        return 'Price Change'
      case 'system_announcement':
        return 'System Announcement'
      default:
        return type
    }
  }

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
            <Text color="gray.600">
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
                onClick={handleMarkAllAsRead}
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
                    setFilterType(e.target.value)
                    setPage(1)
                  }}
                >
                  <option value="trial_ending">Trial Ending</option>
                  <option value="renewal_reminder">Renewal Reminder</option>
                  <option value="weekly_summary">Weekly Summary</option>
                  <option value="monthly_summary">Monthly Summary</option>
                  <option value="inactive_subscription">Inactive Subscription</option>
                  <option value="price_change">Price Change</option>
                  <option value="system_announcement">System Announcement</option>
                </Select>
              </HStack>
              <HStack flex={1} minW="200px">
                <Select
                  placeholder="All notifications"
                  size="sm"
                  value={filterRead}
                  onChange={(e) => {
                    setFilterRead(e.target.value)
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
              <Text fontSize="xl" fontWeight="medium" color="gray.600">
                No notifications found
              </Text>
              <Text color="gray.500">
                {filterType || filterRead ? 'Try adjusting your filters' : 'You are all caught up'}
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
                onClick={() => !notification.is_read && handleMarkAsRead(notification.id)}
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
                            handleMarkAsRead(notification.id)
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
                          handleDelete(notification.id)
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
                <Text fontSize="sm" color="gray.600">
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
    </Container>
  )
}
