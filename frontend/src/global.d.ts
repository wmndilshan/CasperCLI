export {};

declare global {
  interface Window {
    casperDesktop?: { platform: string };
  }
}
