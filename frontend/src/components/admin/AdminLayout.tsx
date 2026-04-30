import {
  Box,
  Flex,
  VStack,
  HStack,
  Text,
  Icon,
  Button,
  Avatar,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuDivider,
  useColorModeValue,
  Heading,
} from '@chakra-ui/react'
import { Link as RouterLink, useLocation, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../contexts/AuthContext'
import {
  FiSettings,
  FiUsers,
  FiActivity,
  FiAlertTriangle,
  FiAlertCircle,
  FiLogOut,
  FiUser,
  FiHome,
  FiBell,
  FiShield,
  FiMessageCircle,
  FiUserPlus,
} from 'react-icons/fi'

interface NavItem {
  labelKey: string
  icon: any
  path: string
}

const ADMIN_NAV_ITEMS: NavItem[] = [
  { labelKey: 'common:admin.configuration', icon: FiSettings, path: '/admin/config' },
  { labelKey: 'common:admin.announcements', icon: FiBell, path: '/admin/announcements' },
  { labelKey: 'common:admin.users', icon: FiUsers, path: '/admin/users' },
  { labelKey: 'common:admin.invites', icon: FiUserPlus, path: '/admin/invites' },
  { labelKey: 'common:admin.logs', icon: FiActivity, path: '/admin/logs' },
  { labelKey: 'common:admin.securityEvents', icon: FiAlertTriangle, path: '/admin/security' },
  { labelKey: 'common:admin.syncErrors', icon: FiAlertCircle, path: '/admin/sync-errors' },
  { labelKey: 'common:admin.ipWhitelist', icon: FiShield, path: '/admin/ip-whitelist' },
  { labelKey: 'common:admin.feedbackMetrics', icon: FiMessageCircle, path: '/admin/feedback-metrics' },
]

export const AdminLayout = () => {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const location = useLocation()
  const bgColor = useColorModeValue('gray.50', 'gray.900')
  const sidebarBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const headerBg = useColorModeValue('white', 'gray.800')

  return (
    <Flex h="100vh" bg={bgColor}>
      {/* Sidebar */}
      <Box
        w="250px"
        bg={sidebarBg}
        borderRightWidth="1px"
        borderColor={borderColor}
        p={6}
      >
        <VStack align="stretch" spacing={6} h="full">
          {/* Logo */}
          <Box>
            <Heading size="md" color="red.500">
              🛡️ {t('common:admin.title')}
            </Heading>
          </Box>

          {/* Return to Dashboard Link */}
          <Button
            as={RouterLink}
            to="/dashboard"
            leftIcon={<Icon as={FiHome} />}
            variant="outline"
            size="sm"
            colorScheme="blue"
          >
            {t('common:admin.returnToDashboard')}
          </Button>

          {/* Navigation */}
          <VStack align="stretch" spacing={1} flex={1}>
            {ADMIN_NAV_ITEMS.map((item) => {
              const isActive = location.pathname === item.path
              return (
                <Button
                  key={item.path}
                  as={RouterLink}
                  to={item.path}
                  leftIcon={<Icon as={item.icon} />}
                  variant={isActive ? 'solid' : 'ghost'}
                  colorScheme={isActive ? 'red' : 'gray'}
                  justifyContent="flex-start"
                >
                  {t(item.labelKey)}
                </Button>
              )
            })}
          </VStack>

          {/* User Menu */}
          <Box borderTopWidth="1px" borderColor={borderColor} pt={4}>
            <Menu>
              <MenuButton as={Button} variant="ghost" w="full">
                <HStack spacing={3}>
                  <Avatar size="sm" name={user?.email} />
                  <VStack align="start" spacing={0} flex={1}>
                    <Text fontSize="sm" fontWeight="medium">
                      {user?.email}
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      {t('common:admin.administrator')}
                    </Text>
                  </VStack>
                </HStack>
              </MenuButton>
              <MenuList>
                <MenuItem icon={<FiUser />}>{t('common:menu.profile')}</MenuItem>
                <MenuDivider />
                <MenuItem icon={<FiLogOut />} onClick={logout}>
                  {t('common:menu.logout')}
                </MenuItem>
              </MenuList>
            </Menu>
          </Box>
        </VStack>
      </Box>

      {/* Main Content */}
      <Flex flex={1} direction="column" overflow="hidden">
        {/* Header */}
        <Box
          bg={headerBg}
          borderBottomWidth="1px"
          borderColor={borderColor}
          px={8}
          py={4}
        >
          <HStack justify="space-between">
            <Heading size="lg">{t('common:admin.title')}</Heading>
            <HStack spacing={4}>
              <Text fontSize="sm" color="gray.500">
                {t('common:admin.lastLogin')}: {new Date().toLocaleDateString()}
              </Text>
            </HStack>
          </HStack>
        </Box>

        {/* Content Area */}
        <Box flex={1} overflow="auto" p={8}>
          <Outlet />
        </Box>
      </Flex>
    </Flex>
  )
}
