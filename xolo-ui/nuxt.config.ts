// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  modules: ['vuetify-nuxt-module'],
  css: ['@mdi/font/css/materialdesignicons.css', '~/assets/main.css'],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:10000/api/v4',
      version: process.env.NUXT_PUBLIC_VERSION || 'development'
    }
  },
  vuetify: {
    vuetifyOptions: {
      theme: {
        defaultTheme: 'xoloDark',
        themes: {
          xoloDark: {
            dark: true,
            colors: {
              background: '#07111f',
              surface: '#0d1b2f',
              'surface-bright': '#172a46',
              'surface-light': '#132540',
              primary: '#62a8ff',
              secondary: '#91c5ff',
              accent: '#38d5f5',
              info: '#60a5fa',
              success: '#45d5a3',
              warning: '#f6c85f',
              error: '#ff718b'
            }
          }
        }
      }
    }
  }
})
