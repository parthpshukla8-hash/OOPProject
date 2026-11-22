import { createDarkTheme, createLightTheme } from '@fluentui/react-components'
import type { BrandVariants, Theme } from '@fluentui/react-components'

// Fluent UI 9 blue brand ramp.
const fluentBlue: BrandVariants = {
  10: '#061724', 20: '#082338', 30: '#0A2E4A', 40: '#0C3B5E', 50: '#0C5078',
  60: '#0E63A9', 70: '#115EA3', 80: '#0F6CBD', 90: '#2886D9', 100: '#479EF5',
  110: '#62ABF5', 120: '#77B7F7', 130: '#96C6FA', 140: '#B4D6FA', 150: '#CFE4FA', 160: '#EBF3FC',
}

const typography = {
  fontFamilyBase: "'Aptos', 'Segoe UI Variable Text', 'Segoe UI', system-ui, -apple-system, sans-serif",
  fontFamilyNumeric: "'Aptos', 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif",
}

export const lightTheme: Theme = {
  ...createLightTheme(fluentBlue),
  ...typography,
}

export const darkTheme: Theme = {
  ...createDarkTheme(fluentBlue),
  ...typography,
}
