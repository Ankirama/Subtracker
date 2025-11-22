import { Box, Container, Heading, Tabs, TabList, TabPanels, Tab, TabPanel, useBreakpointValue } from '@chakra-ui/react'
import { AccountSettingsTab } from './AccountSettingsTab'
import { SecuritySettingsTab } from './SecuritySettingsTab'
import { PreferencesTab } from './PreferencesTab'
import { NotificationSettingsTab } from './NotificationSettingsTab'

export function SettingsPage() {
  const tabVariant = useBreakpointValue({ base: 'soft-rounded', md: 'enclosed' })
  const isMobile = useBreakpointValue({ base: true, md: false })

  return (
    <Container maxW="container.xl" py={{ base: 4, md: 8 }} px={{ base: 4, md: 6 }}>
      <Heading size={{ base: 'md', md: 'lg' }} mb={{ base: 4, md: 6 }}>
        Settings
      </Heading>

      <Tabs
        colorScheme="blue"
        variant={tabVariant}
        orientation={isMobile ? 'horizontal' : 'horizontal'}
        isFitted={isMobile}
      >
        <TabList
          overflowX="auto"
          overflowY="hidden"
          css={{
            scrollbarWidth: 'none',
            '::-webkit-scrollbar': { display: 'none' },
          }}
          mb={{ base: 4, md: 0 }}
        >
          <Tab fontSize={{ base: 'sm', md: 'md' }}>Account</Tab>
          <Tab fontSize={{ base: 'sm', md: 'md' }}>Security</Tab>
          <Tab fontSize={{ base: 'sm', md: 'md' }}>Preferences</Tab>
          <Tab fontSize={{ base: 'sm', md: 'md' }}>Notifications</Tab>
        </TabList>

        <TabPanels>
          <TabPanel px={{ base: 0, md: 4 }}>
            <AccountSettingsTab />
          </TabPanel>

          <TabPanel px={{ base: 0, md: 4 }}>
            <SecuritySettingsTab />
          </TabPanel>

          <TabPanel px={{ base: 0, md: 4 }}>
            <PreferencesTab />
          </TabPanel>

          <TabPanel px={{ base: 0, md: 4 }}>
            <NotificationSettingsTab />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Container>
  )
}
