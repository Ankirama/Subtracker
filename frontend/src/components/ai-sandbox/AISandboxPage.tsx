import { Box, Container, Heading, Tabs, TabList, TabPanels, Tab, TabPanel } from '@chakra-ui/react'
import { ManualTestTab } from './ManualTestTab'
import { ReviewEmailsTab } from './ReviewEmailsTab'

export const AISandboxPage = () => {
  return (
    <Container maxW="container.xl" py={8}>
      <Box mb={6}>
        <Heading size="lg">AI Sandbox</Heading>
      </Box>

      <Tabs colorScheme="blue" variant="enclosed">
        <TabList>
          <Tab>Manual Test</Tab>
          <Tab>Review Uncertain Emails</Tab>
        </TabList>

        <TabPanels>
          <TabPanel px={0}>
            <ManualTestTab />
          </TabPanel>
          <TabPanel px={0}>
            <ReviewEmailsTab />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Container>
  )
}
