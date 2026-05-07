import { useRef, useMemo, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, Environment, Sparkles } from '@react-three/drei';
import * as THREE from 'three';
import { useTheme } from '@/lib/theme';

interface FloatingGeometryProps {
  position: [number, number, number];
  scale: number;
  type: string;
  color: string;
  speed: number;
  mouseRef: React.MutableRefObject<{ x: number, y: number }>;
}

function GeometryMesh({ type, color, scale, mouseRef, speed }: { type: string; color: string; scale: number; mouseRef: React.MutableRefObject<{ x: number, y: number }>; speed: number }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const targetPos = useRef(new THREE.Vector3(0, 0, 0));
  // Store an initial random offset for varied continuous movement
  const offset = useMemo(() => Math.random() * 1000, []);

  useFrame((state) => {
    if (!meshRef.current) return;
    
    // Rotate the mesh slightly every frame
    meshRef.current.rotation.x += 0.002 * speed;
    meshRef.current.rotation.y += 0.003 * speed;

    const time = state.clock.getElapsedTime();

    // 1. Natural floating movement using sine waves
    // Slowed down the time multiplier significantly (from 0.3/0.4 to 0.05/0.07) for a much more peaceful drift
    const floatX = Math.sin(time * speed * 0.05 + offset) * 18;
    const floatY = Math.cos(time * speed * 0.07 + offset) * 12;
    
    // Set base position to the animated floating position
    targetPos.current.set(floatX, floatY, 0);

    // 2. Mouse Repel Logic
    // Get the base position from the parent wrapper
    const parentPos = new THREE.Vector3();
    if (meshRef.current.parent) {
      meshRef.current.parent.getWorldPosition(parentPos);
    }
    
    // Convert normalized mouse coordinates to world space 
    const viewport = state.viewport.getCurrentViewport(state.camera, parentPos);
    const mouseWorldX = (mouseRef.current.x * viewport.width) / 2;
    const mouseWorldY = (mouseRef.current.y * viewport.height) / 2;

    // Calculate distance from mouse to the *target floating position* 
    // (adding parentPos so we calculate relative to world space)
    const worldTargetX = parentPos.x + floatX;
    const worldTargetY = parentPos.y + floatY;

    const dx = worldTargetX - mouseWorldX;
    const dy = worldTargetY - mouseWorldY;
    const distance = Math.sqrt(dx * dx + dy * dy);

    // Responsive interaction radius and strength
    const repelRadius = viewport.width / 4; 
    const maxRepel = 4.0;

    if (distance < repelRadius) {
      const force = Math.pow((repelRadius - distance) / repelRadius, 1.5);
      const angle = Math.atan2(dy, dx);
      // Add the push force to the natural floating target
      targetPos.current.x += Math.cos(angle) * maxRepel * force;
      targetPos.current.y += Math.sin(angle) * maxRepel * force;
    }

    // Smoothly interpolate current local position to the combined target position
    meshRef.current.position.x = THREE.MathUtils.lerp(meshRef.current.position.x, targetPos.current.x, 0.05);
    meshRef.current.position.y = THREE.MathUtils.lerp(meshRef.current.position.y, targetPos.current.y, 0.05);
  });

  return (
    <mesh ref={meshRef} scale={scale}>
      {type === 'box' && <boxGeometry args={[1, 1, 1]} />}
      {type === 'sphere' && <sphereGeometry args={[0.7, 32, 32]} />}
      {type === 'torus' && <torusGeometry args={[0.6, 0.2, 16, 32]} />}
      {type === 'icosahedron' && <icosahedronGeometry args={[0.8, 0]} />}
      {type === 'octahedron' && <octahedronGeometry args={[0.8]} />}
      <meshStandardMaterial 
        color={color} 
        roughness={0.1} 
        metalness={0.8} 
        envMapIntensity={1.5} 
        transparent
        opacity={0.85}
      />
    </mesh>
  );
}

function FloatingGeometry({ position, scale, type, color, speed, mouseRef }: FloatingGeometryProps) {
  return (
    // Lowered floatIntensity so our custom sine wave logic does most of the macroscopic movement
    <Float speed={speed * 0.5} rotationIntensity={1.5} floatIntensity={0.5} position={position}>
      <GeometryMesh type={type} color={color} scale={scale} mouseRef={mouseRef} speed={speed} />
    </Float>
  );
}

function Scene({ mouseRef }: { mouseRef: React.MutableRefObject<{ x: number, y: number }> }) {
  const { theme } = useTheme();
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const checkDark = () => {
      if (theme === 'system') {
        return window.matchMedia('(prefers-color-scheme: dark)').matches;
      }
      return theme === 'dark';
    };
    setIsDark(checkDark());

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => {
      if (theme === 'system') setIsDark(mediaQuery.matches);
    };
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, [theme]);

  // Modern vibrant colors
  const colors = isDark 
    ? ['#4f46e5', '#8b5cf6', '#ec4899', '#0ea5e9', '#10b981']
    : ['#6366f1', '#a855f7', '#f43f5e', '#38bdf8', '#34d399'];
  
  const types = ['box', 'sphere', 'torus', 'icosahedron', 'octahedron'];

  // Generate random shapes once based on theme mode
  const shapes = useMemo(() => {
    return Array.from({ length: 5 }).map((_, i) => ({
      id: i,
      position: [
        (Math.random() - 0.5) * 35,
        (Math.random() - 0.5) * 25,
        (Math.random() - 0.5) * 15 - 8
      ] as [number, number, number],
      scale: Math.random() * 2.5 + 1.2,
      type: types[i % types.length], // Ensure we get a variety of shapes
      color: colors[i % colors.length], // Ensure we get a variety of colors
      speed: Math.random() * 1.0 + 0.3 // Slightly slower movement for fewer objects
    }));
  }, [isDark]); // Re-generate colors when theme changes

  return (
    <>
      <ambientLight intensity={isDark ? 0.3 : 0.8} />
      <directionalLight position={[10, 10, 5]} intensity={1.5} color={isDark ? "#ffffff" : "#fdf4ff"} />
      <directionalLight position={[-10, -10, -5]} intensity={0.5} color={isDark ? "#818cf8" : "#c084fc"} />
      
      {shapes.map((shape) => (
        <FloatingGeometry key={shape.id} {...shape} mouseRef={mouseRef} />
      ))}

      <Sparkles 
        count={50} 
        scale={30} 
        size={2} 
        speed={0.2} 
        opacity={isDark ? 0.3 : 0.5} 
        color={isDark ? '#cbd5e1' : '#64748b'} 
      />
      
      <Environment preset="city" />
    </>
  );
}

export function Background3D() {
  const mouseRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      // Normalize mouse coordinates (-1 to +1)
      mouseRef.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouseRef.current.y = -(e.clientY / window.innerHeight) * 2 + 1;
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <div className="fixed inset-0 pointer-events-none -z-10 bg-transparent overflow-hidden">
      <Canvas camera={{ position: [0, 0, 15], fov: 45 }}>
        <Scene mouseRef={mouseRef} />
      </Canvas>
      {/* Overlay to ensure app readability while preserving 3D background sharpness */}
      <div className="absolute inset-0 bg-background/50 dark:bg-background/50 backdrop-blur-[1px] mask-gradient"></div>
    </div>
  );
}
