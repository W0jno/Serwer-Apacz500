import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';

const SessionGraph = ({ graph }) => {
  // graph is expected to be { devices: [], matrix: [] }
  const devices = graph?.devices || [];
  const matrix = graph?.matrix || [];
  
  const radius = 150; // Radius of the circle
  const containerSize = 400; // Size of the container box

  if (!devices || devices.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: containerSize, mt: 4 }}>
        <Typography variant="h6" color="text.secondary">
          No active session
        </Typography>
      </Box>
    );
  }

  const getPosition = (index) => {
    const angle = (index / devices.length) * 2 * Math.PI - (Math.PI / 2); // Start from top
    const x = containerSize / 2 + radius * Math.cos(angle);
    const y = containerSize / 2 + radius * Math.sin(angle);
    return { x, y };
  };

  const nodePositions = devices.reduce((acc, deviceId, index) => {
    acc[deviceId] = getPosition(index);
    return acc;
  }, {});

  return (
    <Box sx={{ position: 'relative', width: containerSize, height: containerSize, margin: 'auto', mt: 4 }}>
      {/* Edges */}
      {matrix.map((row, sourceIndex) => (
        row.map((prob, targetIndex) => {
          if (prob <= 0) return null;

          const sourceId = devices[sourceIndex];
          const targetId = devices[targetIndex];
          const start = nodePositions[sourceId];
          const end = nodePositions[targetId];

          const dx = end.x - start.x;
          const dy = end.y - start.y;
          const angle = Math.atan2(dy, dx);
          const distance = Math.sqrt(dx * dx + dy * dy);
          
          // Calculate arrow rotation
          const arrowRot = (angle * 180) / Math.PI;

          // Adjust line to stop before the node (node width ~100px, so 50px half-width)
          // Actually, let's just draw lines between centers and rely on z-index or simple overlay
          
          return (
            <React.Fragment key={`edge-${sourceId}-${targetId}`}>
               {/* Line */}
               <Box
                sx={{
                  position: 'absolute',
                  left: start.x,
                  top: start.y,
                  width: distance,
                  height: 2,
                  bgcolor: prob >= 1.0 ? 'primary.main' : 'warning.main',
                  opacity: prob, // Opacity based on probability
                  transform: `rotate(${arrowRot}deg)`,
                  transformOrigin: '0 0',
                  zIndex: 1,
                  pointerEvents: 'none',
                }}
              />
              {/* Arrow Head (roughly in the middle or end) */}
               <ArrowForwardIcon
                sx={{
                  position: 'absolute',
                  left: start.x + (dx * 0.6), // 60% of the way
                  top: start.y + (dy * 0.6),
                  transform: `translate(-50%, -50%) rotate(${arrowRot}deg)`,
                  color: prob >= 1.0 ? 'primary.main' : 'warning.main',
                  opacity: prob,
                  zIndex: 1,
                  fontSize: 16
                }}
              />
               {/* Probability Label */}
               {prob < 1.0 && (
                 <Typography
                   variant="caption"
                   sx={{
                     position: 'absolute',
                     left: start.x + (dx * 0.5),
                     top: start.y + (dy * 0.5) - 10,
                     transform: 'translate(-50%, -50%)',
                     bgcolor: 'background.paper',
                     px: 0.5,
                     borderRadius: 1,
                     border: '1px solid #eee',
                     fontSize: '0.65rem',
                     zIndex: 2,
                   }}
                 >
                   {prob.toFixed(2)}
                 </Typography>
               )}
            </React.Fragment>
          );
        })
      ))}

      {/* Nodes */}
      {devices.map((deviceId) => {
        const pos = nodePositions[deviceId];
        return (
          <Paper
            key={deviceId}
            elevation={3}
            sx={{
              position: 'absolute',
              left: pos.x,
              top: pos.y,
              transform: 'translate(-50%, -50%)',
              width: 100,
              height: 50,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              borderRadius: 2,
              zIndex: 10, // Above lines
              border: '1px solid #e0e0e0'
            }}
          >
            <Typography variant="body2" noWrap sx={{ maxWidth: '90%' }}>
                {deviceId}
            </Typography>
          </Paper>
        );
      })}
    </Box>
  );
};

export default SessionGraph;