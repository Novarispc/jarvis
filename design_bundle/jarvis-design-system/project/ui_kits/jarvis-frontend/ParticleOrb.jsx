// Particle-based animated orb with multiple states
const ParticleOrb = ({ state = 'idle' }) => {
  const canvasRef = React.useRef(null);
  const animationRef = React.useRef(null);
  const particlesRef = React.useRef([]);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const centerX = width / 2;
    const centerY = height / 2;

    // Particle class
    class Particle {
      constructor(state) {
        this.reset(state);
      }

      reset(state) {
        const angle = Math.random() * Math.PI * 2;
        const baseRadius = state === 'listening' ? 180 : state === 'thinking' ? 120 : 80;
        const radiusVariation = state === 'listening' ? 60 : 40;
        const distance = baseRadius + Math.random() * radiusVariation;
        
        this.x = centerX + Math.cos(angle) * distance;
        this.y = centerY + Math.sin(angle) * distance;
        this.baseX = this.x;
        this.baseY = this.y;
        
        this.vx = (Math.random() - 0.5) * 0.5;
        this.vy = (Math.random() - 0.5) * 0.5;
        
        this.life = 1;
        this.decay = 0.002 + Math.random() * 0.003;
        
        this.size = state === 'listening' ? 2.5 : 2;
        this.color = this.getColor();
        
        // Connection behavior
        this.connectionRadius = state === 'listening' ? 80 : 60;
      }

      getColor() {
        const r = 255;
        const g = Math.floor(140 + Math.random() * 60);
        const b = Math.floor(0 + Math.random() * 50);
        return `rgba(${r}, ${g}, ${b}, ${this.life})`;
      }

      update(state) {
        // Gentle drift
        this.x += this.vx;
        this.y += this.vy;
        
        // Orbital pull back to base
        const dx = this.baseX - this.x;
        const dy = this.baseY - this.y;
        this.vx += dx * 0.01;
        this.vy += dy * 0.01;
        
        // Velocity damping
        this.vx *= 0.95;
        this.vy *= 0.95;
        
        this.life -= this.decay;
        this.color = this.getColor();
        
        if (this.life <= 0) {
          this.reset(state);
        }
      }

      draw(ctx) {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = this.color;
        ctx.fill();
        
        // Add glow
        ctx.shadowBlur = 8;
        ctx.shadowColor = 'rgba(255, 180, 50, 0.8)';
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    }

    // Initialize particles based on state
    const getParticleCount = (state) => {
      if (state === 'listening') return 800;
      if (state === 'thinking') return 500;
      return 300;
    };

    const initParticles = (state) => {
      const count = getParticleCount(state);
      const particles = [];
      for (let i = 0; i < count; i++) {
        particles.push(new Particle(state));
      }
      return particles;
    };

    particlesRef.current = initParticles(state);

    // Animation loop
    const animate = () => {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
      ctx.fillRect(0, 0, width, height);

      const particles = particlesRef.current;

      // Draw connections
      ctx.strokeStyle = 'rgba(255, 180, 50, 0.15)';
      ctx.lineWidth = 0.5;
      
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          
          if (dist < particles[i].connectionRadius) {
            const opacity = (1 - dist / particles[i].connectionRadius) * 0.3;
            ctx.strokeStyle = `rgba(255, 180, 50, ${opacity})`;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }

      // Update and draw particles
      particles.forEach(particle => {
        particle.update(state);
        particle.draw(ctx);
      });

      // Draw center glow
      const gradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, 100);
      gradient.addColorStop(0, 'rgba(255, 220, 100, 0.3)');
      gradient.addColorStop(0.5, 'rgba(255, 150, 50, 0.1)');
      gradient.addColorStop(1, 'transparent');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [state]);

  return (
    <canvas
      ref={canvasRef}
      width={500}
      height={500}
      style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        pointerEvents: 'none'
      }}
    />
  );
};

window.ParticleOrb = ParticleOrb;
