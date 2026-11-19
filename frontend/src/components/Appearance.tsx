import { useLayoutEffect, type ReactNode } from 'react';
import { Button, FluentProvider, createDarkTheme, createLightTheme, type BrandVariants } from '@fluentui/react-components';
import { WeatherMoon20Regular, WeatherSunny20Regular } from '@fluentui/react-icons';
import { usePreferences } from '../store/preferences';

const evergreen: BrandVariants = {
  10: '#001b12', 20: '#00281c', 30: '#003625', 40: '#004430',
  50: '#00513a', 60: '#005c43', 70: '#08654e', 80: '#087459',
  90: '#138467', 100: '#239576', 110: '#37a687', 120: '#51b899',
  130: '#71cbad', 140: '#92ddc1', 150: '#b6edda', 160: '#dcf8ed',
};
const light = createLightTheme(evergreen);
const dark = {
  ...createDarkTheme(evergreen),
  colorNeutralBackground1: '#101c1b', colorNeutralBackground2: '#142321',
  colorBrandForeground1: '#66edbd', colorBrandForegroundLink: '#7febca',
};

export function Appearance({ children }: { children: ReactNode }) {
  const { darkMode, bigText, highContrast, reduceMotion } = usePreferences();
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = darkMode ? 'dark' : 'light';
    document.body.classList.toggle('big-text', bigText);
    document.body.classList.toggle('high-contrast', highContrast);
    document.body.classList.toggle('no-motion', reduceMotion);
  }, [darkMode, bigText, highContrast, reduceMotion]);
  return <FluentProvider theme={darkMode ? dark : light} className="app-appearance">{children}</FluentProvider>;
}

export function ThemeToggle() {
  const { darkMode, setPref } = usePreferences();
  return <Button appearance="subtle" shape="circular" aria-label="Modo nocturno" title={darkMode ? 'Usar modo claro' : 'Usar modo nocturno'}
    aria-pressed={darkMode} icon={darkMode ? <WeatherSunny20Regular /> : <WeatherMoon20Regular />}
    onClick={() => setPref('darkMode', !darkMode)} />;
}
