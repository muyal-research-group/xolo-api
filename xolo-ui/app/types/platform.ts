export type PlatformRole = 'admin' | 'user' | 'guest'

export interface PlatformUser {
  user_id: string
  username: string
  role: PlatformRole
  permissions: string[]
  allowed_account_ids: string[]
  is_active: boolean
  must_change_password: boolean
  created_at: string
  updated_at: string
  last_login_at: string | null
}

export interface Account {
  account_id: string
  name: string
  is_active: boolean
  timezone: string
  created_at: string
  updated_at: string
}

export interface PlatformOptions {
  roles: PlatformRole[]
  permissions: string[]
}
