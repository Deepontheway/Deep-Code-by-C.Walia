import React from 'react';
import { render, Box, Text } from 'ink';
import { getDefaultModel } from '../models/index.js';

export function startTUI() {
  const App = () => (
    <Box flexDirection="column" padding={1}>
      <Text color="green">Deep Code by C.Walia</Text>
      <Text>AGI-style autonomous coding agent</Text>
      <Text>Default Model: {getDefaultModel()}</Text>
      <Text color="cyan">Type /help for commands | /model to switch | /plan for task plan</Text>
    </Box>
  );
  render(<App />);
}
