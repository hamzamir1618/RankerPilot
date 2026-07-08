Run pnpm run lint
  pnpm run lint
  shell: /usr/bin/bash -e {0}
  env:
    PNPM_HOME: /home/runner/setup-pnpm/node_modules/.bin
    UV_CACHE_DIR: /home/runner/work/_temp/setup-uv-cache

> rankerpilot@ lint /home/runner/work/RankerPilot/RankerPilot
> pnpm -r run lint

Scope: 2 of 3 workspace projects
apps/web lint$ eslint
apps/web lint: /home/runner/work/RankerPilot/RankerPilot/apps/web/src/app/(app)/projects/[projectId]/audits/[auditId]/page.tsx
apps/web lint:   14:9  warning  'projectId' is assigned a value but never used  @typescript-eslint/no-unused-vars
apps/web lint: /home/runner/work/RankerPilot/RankerPilot/apps/web/src/app/(app)/projects/page.tsx
apps/web lint:    3:10  warning  'useQuery' is defined but never used      @typescript-eslint/no-unused-vars
apps/web lint:   29:62  error    Unexpected any. Specify a different type  @typescript-eslint/no-explicit-any
apps/web lint:   32:28  error    Unexpected any. Specify a different type  @typescript-eslint/no-explicit-any
apps/web lint:   33:63  error    Unexpected any. Specify a different type  @typescript-eslint/no-explicit-any
apps/web lint:   37:14  warning  'err' is defined but never used           @typescript-eslint/no-unused-vars
apps/web lint: /home/runner/work/RankerPilot/RankerPilot/apps/web/src/app/(marketing)/login/page.tsx
apps/web lint:   29:34  error  Unexpected any. Specify a different type                         @typescript-eslint/no-explicit-any
apps/web lint:   41:19  error  Unexpected any. Specify a different type                         @typescript-eslint/no-explicit-any
apps/web lint:   83:16  error  `'` can be escaped with `&apos;`, `&lsquo;`, `&#39;`, `&rsquo;`  react/no-unescaped-entities
apps/web lint: /home/runner/work/RankerPilot/RankerPilot/apps/web/src/app/(marketing)/register/page.tsx
apps/web lint:   30:34  error  Unexpected any. Specify a different type  @typescript-eslint/no-explicit-any
apps/web lint:   41:19  error  Unexpected any. Specify a different type  @typescript-eslint/no-explicit-any
apps/web lint: /home/runner/work/RankerPilot/RankerPilot/apps/web/src/components/findings-table.tsx
apps/web lint:    9:78  warning  'Info' is defined but never used          @typescript-eslint/no-unused-vars
apps/web lint:   84:35  error    Unexpected any. Specify a different type  @typescript-eslint/no-explicit-any
apps/web lint: /home/runner/work/RankerPilot/RankerPilot/apps/web/src/lib/sse.ts
apps/web lint:   12:18  error  Unexpected any. Specify a different type  @typescript-eslint/no-explicit-any
apps/web lint: ✖ 14 problems (10 errors, 4 warnings)
apps/web lint: Failed
/home/runner/work/RankerPilot/RankerPilot/apps/web:
 ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL  web@0.1.0 lint: `eslint`
Exit status 1
 ELIFECYCLE  Command failed with exit code 1.
Error: Process completed with exit code 1.
