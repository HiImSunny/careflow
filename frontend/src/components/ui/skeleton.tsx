/**
 * Skeleton — animated loading placeholder component.
 * Follows the shadcn/ui Skeleton pattern.
 */

import React from 'react';

export function Skeleton({
  className = '',
  ...props
}: React.HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return (
    <div
      className={`animate-pulse rounded-md bg-slate-200 ${className}`}
      {...props}
    />
  );
}

export default Skeleton;
