import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';

const SessionGraph = ({ graph }) => {
  const nodes = Object.keys(graph);
  const radius = 150; // Radius of the circle
  const containerSize = 400; // Size of the container box

  if (nodes.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: containerSize, mt: 4 }}>
        <Typography variant="h6" color="text.secondary">
          No active session
        </Typography>
      </Box>
    );
  }

  const getPosition = (index) => {
    const angle = (index / nodes.length) * 2 * Math.PI;
    const x = containerSize / 2 + radius * Math.cos(angle);
    const y = containerSize / 2 + radius * Math.sin(angle);
    return { x, y };
  };

  const nodePositions = nodes.reduce((acc, node, index) => {
    acc[node] = getPosition(index);
    return acc;
  }, {});

  return (
    <Box sx={{ position: 'relative', width: containerSize, height: containerSize, margin: 'auto', mt: 4 }}>
      {nodes.map((nodeId) => {
        const pos = nodePositions[nodeId];
        const targetId = graph[nodeId];
        const targetPos = nodePositions[targetId];

        const angle = Math.atan2(targetPos.y - pos.y, targetPos.x - pos.x);
        const arrowRot = (angle * 180) / Math.PI;

        return (
          <React.Fragment key={nodeId}>
            {/* Node */}
            <Paper
              elevation={3}
              sx={{
                position: 'absolute',
                left: pos.x - 50,
                top: pos.y - 25,
                width: 100,
                height: 50,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                borderRadius: 2,
              }}
            >
              <Typography variant="body2">{nodeId.replace('sim_device_', 'Device ')}</Typography>
            </Paper>

            {/* Arrow */}
            {targetPos && (
              <ArrowForwardIcon
                sx={{
                  position: 'absolute',
                  left: pos.x,
                  top: pos.y,
                  transform: `translate(-50%, -50%) rotate(${arrowRot}deg) translateX(70px)`,
                  color: 'primary.main',
                }}
              />
            )}
          </React.Fragment>
        );
      })}
    </Box>
  );
};

export default SessionGraph;
