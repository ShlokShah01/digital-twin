import { cn } from "cn"

function Skeleton({
  className,
  ...props
}) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted-well", className)}
      {...props}
    />
  )
}

export { Skeleton }
