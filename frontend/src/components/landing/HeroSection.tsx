import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  Button,
  useColorModeValue,
} from '@chakra-ui/react'
import { useTranslation } from 'react-i18next'
import { Link as RouterLink } from 'react-router-dom'
import { WaitlistForm } from './WaitlistForm'

export const HeroSection = () => {
  const { t } = useTranslation()
  const bgGradient = useColorModeValue(
    'linear(to-br, blue.50, purple.50)',
    'linear(to-br, blue.900, purple.900)'
  )

  return (
    <Box bg={bgGradient} py={20} minH="85vh" display="flex" alignItems="center">
      <Container maxW="container.xl">
        <VStack spacing={8} textAlign="center">
          <Heading
            as="h1"
            size="3xl"
            fontWeight="bold"
            bgGradient="linear(to-r, blue.400, purple.500)"
            bgClip="text"
            lineHeight="1.2"
          >
            {t('landing:hero.title')}
          </Heading>

          <Text fontSize="xl" color="gray.600" _dark={{ color: 'gray.300' }} maxW="2xl">
            {t('landing:hero.subtitle')}
          </Text>

          <Box w="full" maxW="md" pt={4}>
            <WaitlistForm />
          </Box>

          <Text fontSize="sm" color="gray.500" _dark={{ color: 'gray.400' }}>
            {t('landing:hero.alreadyHaveCode')}{' '}
            <Button
              as={RouterLink}
              to="/login"
              variant="link"
              colorScheme="blue"
              fontSize="sm"
            >
              {t('common:actions.login')}
            </Button>
          </Text>
        </VStack>
      </Container>
    </Box>
  )
}
