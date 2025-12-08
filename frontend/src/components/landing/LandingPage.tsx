import { Box, Container, Text, HStack, useColorModeValue } from '@chakra-ui/react'
import { useTranslation } from 'react-i18next'
import { HeroSection } from './HeroSection'
import { FeatureCards } from './FeatureCards'
import { AppShowcase } from './AppShowcase'
import { HowItWorks } from './HowItWorks'
import { TrustSection } from './TrustSection'

export const LandingPage = () => {
  const { t } = useTranslation()
  const footerBg = useColorModeValue('gray.100', 'gray.900')
  const currentYear = new Date().getFullYear()

  return (
    <Box minH="100vh">
      <HeroSection />
      <FeatureCards />
      <AppShowcase />
      <HowItWorks />
      <TrustSection />

      {/* Footer */}
      <Box bg={footerBg} py={8} borderTopWidth="1px">
        <Container maxW="container.xl">
          <HStack justify="space-between" flexWrap="wrap" spacing={4}>
            <Text fontSize="sm" color="gray.600" _dark={{ color: 'gray.400' }}>
              © {currentYear} Subscription Tracker. {t('landing:footer.rights')}
            </Text>
            <Text fontSize="sm" color="gray.500" _dark={{ color: 'gray.500' }}>
              {t('landing:footer.tagline')}
            </Text>
          </HStack>
        </Container>
      </Box>
    </Box>
  )
}
