import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Button,
  Icon,
  Text,
  useToast,
  HStack,
} from '@chakra-ui/react'
import { FiGlobe, FiCheck } from 'react-icons/fi'
import { useMutation } from '@tanstack/react-query'
import { authAPI } from '../../api/auth'
import { setLanguage } from '../../i18n/detector'

interface LanguageSwitcherProps {
  variant?: 'menu' | 'buttons'
  size?: 'sm' | 'md' | 'lg'
}

export const LanguageSwitcher = ({ variant = 'menu', size = 'md' }: LanguageSwitcherProps) => {
  const { i18n, t } = useTranslation('common')
  const toast = useToast()
  const [isChanging, setIsChanging] = useState(false)

  const languageMutation = useMutation({
    mutationFn: (language: string) => authAPI.updateLanguagePreference(language),
    onSuccess: () => {
      toast({
        title: t('success'),
        description: t('settings:language.saveSuccess'),
        status: 'success',
        duration: 3000,
        isClosable: true,
      })
    },
    onError: () => {
      toast({
        title: t('error'),
        description: t('settings:language.saveError'),
        status: 'error',
        duration: 5000,
        isClosable: true,
      })
    },
  })

  const changeLanguage = async (lang: string) => {
    setIsChanging(true)
    try {
      // Change i18next language immediately for instant UI update
      await i18n.changeLanguage(lang)

      // Update localStorage
      setLanguage(lang as 'en' | 'fr')

      // Update backend preference (if authenticated)
      try {
        await languageMutation.mutateAsync(lang)
      } catch (error) {
        // Silent fail for backend update - language still changed locally
        console.warn('Failed to update language preference in backend:', error)
      }
    } finally {
      setIsChanging(false)
    }
  }

  const languages = [
    { code: 'en', label: 'English', flag: '🇬🇧' },
    { code: 'fr', label: 'Français', flag: '🇫🇷' },
  ]

  const currentLanguage = languages.find(lang => lang.code === i18n.language) || languages[0]

  if (variant === 'buttons') {
    return (
      <HStack spacing={2}>
        {languages.map(lang => (
          <Button
            key={lang.code}
            size={size}
            variant={i18n.language === lang.code ? 'solid' : 'outline'}
            colorScheme={i18n.language === lang.code ? 'blue' : 'gray'}
            onClick={() => changeLanguage(lang.code)}
            isLoading={isChanging && i18n.language !== lang.code}
            leftIcon={i18n.language === lang.code ? <Icon as={FiCheck} /> : undefined}
          >
            <Text>{lang.flag} {lang.label}</Text>
          </Button>
        ))}
      </HStack>
    )
  }

  return (
    <Menu>
      <MenuButton
        as={Button}
        size={size}
        variant="ghost"
        leftIcon={<Icon as={FiGlobe} />}
        isLoading={isChanging}
      >
        {currentLanguage.flag} {currentLanguage.label}
      </MenuButton>
      <MenuList>
        {languages.map(lang => (
          <MenuItem
            key={lang.code}
            onClick={() => changeLanguage(lang.code)}
            icon={i18n.language === lang.code ? <Icon as={FiCheck} /> : undefined}
            fontWeight={i18n.language === lang.code ? 'bold' : 'normal'}
          >
            {lang.flag} {lang.label}
          </MenuItem>
        ))}
      </MenuList>
    </Menu>
  )
}
