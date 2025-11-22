import { useState } from 'react'
import { Avatar, AvatarProps } from '@chakra-ui/react'
import { getProviderLogoUrl, getProviderInitials } from '../../utils/providerLogos'

interface ProviderLogoProps extends Omit<AvatarProps, 'name' | 'src'> {
  providerName: string
  customLogoUrl?: string | null
}

export const ProviderLogo = ({
  providerName,
  customLogoUrl,
  size = 'sm',
  ...avatarProps
}: ProviderLogoProps) => {
  const [imageError, setImageError] = useState(false)

  // Use custom logo URL if provided, otherwise get from Clearbit
  const logoUrl = customLogoUrl || getProviderLogoUrl(providerName)

  // If image failed to load or no URL, use initials
  const initials = getProviderInitials(providerName)

  return (
    <Avatar
      name={providerName}
      src={imageError ? undefined : logoUrl || undefined}
      onError={() => setImageError(true)}
      size={size}
      bg={imageError || !logoUrl ? 'blue.500' : 'white'}
      color={imageError || !logoUrl ? 'white' : 'gray.800'}
      {...avatarProps}
    >
      {imageError || !logoUrl ? initials : null}
    </Avatar>
  )
}
