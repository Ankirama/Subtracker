import { useState, useEffect } from 'react'
import {
  Box,
  IconButton,
  Badge,
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverHeader,
  PopoverBody,
  PopoverFooter,
  VStack,
  Text,
  Button,
  Divider,
  HStack,
  Icon,
  useToast,
  Spinner,
  Center,
  useColorModeValue,
} from '@chakra-ui/react'
import { FiBell, FiCheck, FiX, FiSettings } from 'react-icons/fi'
import { notificationsApi, Notification } from '../../api/notifications'
import { Link as RouterLink } from 'react-router-dom'
import { formatDistanceToNow } from '../../utils/timeFormat'

export const NotificationBell = () => {
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const toast = useToast()

  const bgColor = useColorModeValue('white', 'gray.800')
  const hoverBg = useColorModeValue('gray.50', 'gray.700')
  const borderColor = useColorModeValue('gray.200', 'gray.600')

  // Fetch unread count on mount and set up polling
  useEffect(() => {
    fetchUnreadCount()
    const interval = setInterval(fetchUnreadCount, 60000) // Poll every minute
    return () => clearInterval(interval)
  }, [])

  // Fetch notifications when popover opens
  useEffect(() => {
    if (isOpen) {
      fetchNotifications()
    }
  }, [isOpen])

  const fetchUnreadCount = async () => {
    try {
      const data = await notificationsApi.getUnreadCount()
      setUnreadCount(data.unread_count)
    } catch (error) {
      console.error('Failed to fetch unread count:', error)
    }
  }

  const fetchNotifications = async () => {
    setIsLoading(true)
    try {
      const data = await notificationsApi.getNotifications({
        page: 1,
        page_size: 10,
      })
      setNotifications(data.notifications)
      setUnreadCount(data.unread_count)
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
    try {
      await notificationsApi.deleteNotification(notificationId)
      setNotifications((prev) => prev.filter((n) => n.id !== notificationId))
      if (!notifications.find((n) => n.id === notificationId)?.is_read) {
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
      case 'TRIAL_ENDING':
        return '⚠️'
      case 'RENEWAL_REMINDER':
        return '🔔'
      case 'WEEKLY_SUMMARY':
        return '📊'
      case 'MONTHLY_SUMMARY':
        return '📈'
      case 'INACTIVE_SUBSCRIPTION':
        return '⏸️'
      case 'PRICE_CHANGE':
        return '💰'
      case 'SYSTEM_ANNOUNCEMENT':
        return '📢'
      case 'SYNC_PREVIEW_AVAILABLE':
        return '🔍'
      default:
        return '📬'
    }
  }

  return (
    <Popover
      isOpen={isOpen}
      onOpen={() => setIsOpen(true)}
      onClose={() => setIsOpen(false)}
      placement="bottom-end"
    >
      <PopoverTrigger>
        <Box position="relative" display="inline-block">
          <IconButton
            aria-label="Notifications"
            icon={<FiBell />}
            variant="ghost"
            size="lg"
          />
          {unreadCount > 0 && (
            <Badge
              colorScheme="red"
              variant="solid"
              position="absolute"
              top="0"
              right="0"
              borderRadius="full"
              fontSize="xs"
            >
              {unreadCount > 99 ? '99+' : unreadCount}
            </Badge>
          )}
        </Box>
      </PopoverTrigger>

      <PopoverContent w="400px" bg={bgColor} borderColor={borderColor}>
        <PopoverHeader fontWeight="bold" borderColor={borderColor}>
          <HStack justify="space-between">
            <Text>Notifications</Text>
            <HStack spacing={2}>
              {unreadCount > 0 && (
                <Button
                  size="xs"
                  variant="ghost"
                  leftIcon={<Icon as={FiCheck} />}
                  onClick={handleMarkAllAsRead}
                >
                  Mark all read
                </Button>
              )}
              <IconButton
                as={RouterLink}
                to="/notifications/settings"
                aria-label="Notification settings"
                icon={<FiSettings />}
                size="sm"
                variant="ghost"
                onClick={() => setIsOpen(false)}
              />
            </HStack>
          </HStack>
        </PopoverHeader>

        <PopoverBody maxH="500px" overflowY="auto" p={0}>
          {isLoading ? (
            <Center py={8}>
              <Spinner />
            </Center>
          ) : notifications.length === 0 ? (
            <Center py={8}>
              <VStack spacing={2}>
                <Text fontSize="3xl">🔕</Text>
                <Text color="gray.500">No notifications</Text>
              </VStack>
            </Center>
          ) : (
            <VStack spacing={0} align="stretch">
              {notifications.map((notification, index) => (
                <Box key={notification.id}>
                  {index > 0 && <Divider />}
                  <HStack
                    p={4}
                    spacing={3}
                    align="start"
                    bg={notification.is_read ? 'transparent' : hoverBg}
                    _hover={{ bg: hoverBg }}
                    cursor="pointer"
                    onClick={() => !notification.is_read && handleMarkAsRead(notification.id)}
                  >
                    <Text fontSize="2xl">{getNotificationIcon(notification.type)}</Text>
                    <VStack align="start" flex={1} spacing={1}>
                      <HStack justify="space-between" w="full">
                        <Text
                          fontWeight={notification.is_read ? 'normal' : 'bold'}
                          fontSize="sm"
                        >
                          {notification.title}
                        </Text>
                        <Badge
                          colorScheme={getPriorityColor(notification.priority)}
                          fontSize="xs"
                        >
                          {notification.priority}
                        </Badge>
                      </HStack>
                      <Text fontSize="xs" color="text.subtle" noOfLines={2}>
                        {notification.message}
                      </Text>
                      <Text fontSize="xs" color="gray.500">
                        {formatDistanceToNow(new Date(notification.created_at))}
                      </Text>
                    </VStack>
                    <IconButton
                      aria-label="Delete notification"
                      icon={<FiX />}
                      size="xs"
                      variant="ghost"
                      colorScheme="red"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(notification.id)
                      }}
                    />
                  </HStack>
                </Box>
              ))}
            </VStack>
          )}
        </PopoverBody>

        {notifications.length > 0 && (
          <PopoverFooter borderColor={borderColor}>
            <Button
              as={RouterLink}
              to="/notifications"
              size="sm"
              variant="ghost"
              w="full"
              onClick={() => setIsOpen(false)}
            >
              View all notifications
            </Button>
          </PopoverFooter>
        )}
      </PopoverContent>
    </Popover>
  )
}
