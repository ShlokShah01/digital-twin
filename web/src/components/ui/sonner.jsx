import { useEffect, useState } from "react"
import { Toaster as Sonner } from "sonner";
import { CheckCircle, Info, WarningOctagon, XCircle, CircleNotch } from "@phosphor-icons/react"

const systemTheme = () =>
  typeof window !== "undefined" &&
  window.matchMedia &&
  window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark"

function useSystemTheme() {
  const [theme, setTheme] = useState(systemTheme)

  useEffect(() => {
    if (!window.matchMedia) return
    const mq = window.matchMedia("(prefers-color-scheme: light)")
    const onChange = () => setTheme(mq.matches ? "light" : "dark")
    mq.addEventListener?.("change", onChange)
    return () => mq.removeEventListener?.("change", onChange)
  }, [])

  return theme
}

const Toaster = (props) => {
  const theme = useSystemTheme()

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      icons={{
        success: (
          <CheckCircle size={16} weight="fill" />
        ),
        info: (
          <Info size={16} />
        ),
        warning: (
          <WarningOctagon size={16} />
        ),
        error: (
          <XCircle size={16} />
        ),
        loading: (
          <CircleNotch size={16} className="animate-spin" />
        ),
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--error-bg": "var(--popover)",
          "--error-border": "color-mix(in oklab, var(--destructive) 50%, var(--border))",
          "--error-text": "var(--popover-foreground)",
          "--success-bg": "var(--popover)",
          "--success-border": "color-mix(in oklab, var(--accent) 55%, var(--border))",
          "--success-text": "var(--popover-foreground)",
          "--border-radius": "var(--radius)"
        }
      }
      toastOptions={{
        classNames: {
          toast: "cn-toast font-sans",
        },
      }}
      {...props}
    />
  );
}

export { Toaster }