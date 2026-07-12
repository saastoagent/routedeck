# React package verification

The bounded functional component smoke lives in the Medusa consumer at
`examples/medusa-agent/frontend/src/tests/app-shell.test.tsx`. It exercises this
package through the public workspace export rather than duplicating a second
primitive-only suite.
