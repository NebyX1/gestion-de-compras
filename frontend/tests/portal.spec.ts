import { expect, test } from '@playwright/test';

// Requiere la semilla local. Ninguna de estas pruebas envía una oferta.
test('el proveedor conserva su cotización al revisar el formulario', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Filtrar por estado' }).selectOption('open');
  await page.getByRole('link', { name: 'Luminarias LED para espacios públicos', exact: true }).click();
  await page.getByRole('link', { name: 'Presentar oferta' }).click();
  await page.getByLabel('Razón social').fill('Empresa de prueba');
  await page.getByLabel('RUT o identificación fiscal').fill('TEST-123456');
  await page.getByLabel('Correo del proveedor').fill('proveedor@example.invalid');
  await page.getByRole('button', { name: 'Continuar' }).click();
  const price = page.getByLabel('Precio unitario (UYU)');
  await price.fill('125.50');
  await page.getByLabel('IVA (%)').fill('22');
  await page.getByLabel('Plazo de entrega (días)').fill('10');
  await page.getByLabel('Garantía (meses)').fill('36');
  await page.getByLabel('Descripción técnica').fill('Luminaria apta para espacios públicos según el pliego.');
  await page.getByRole('button', { name: 'Continuar' }).click();
  await expect(page.getByRole('heading', { name: 'Revisión y envío' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Confirmar y presentar' })).toBeDisabled();
  await page.getByRole('button', { name: 'Atrás' }).click();
  await expect(price).toHaveValue('125.50');
});

test('la adjudicación y el tema nocturno están disponibles sin ingresar al escritorio', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/resultados');
  await page.getByRole('button', { name: 'Modo nocturno' }).click();
  await page.getByRole('link', { name: 'Señalización para cruces escolares', exact: true }).click();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('heading', { name: 'Resultado de la adjudicación' })).toBeVisible();
  await expect(page.getByText('Proveedor adjudicatario', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Presentar oferta' })).toHaveCount(0);
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(fits).toBe(true);
});
