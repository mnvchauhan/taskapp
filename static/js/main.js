// Global Javascript helper functions for AttaPoll Clone

document.addEventListener('DOMContentLoaded', () => {
    // 1. Auto-dismiss Flask flash messages beautifully
    const flashContainer = document.getElementById('flashContainer');
    if (flashContainer) {
        setTimeout(() => {
            const flashes = flashContainer.querySelectorAll('.flash-message');
            flashes.forEach((flash, index) => {
                setTimeout(() => {
                    // Set transitions
                    flash.style.transition = 'opacity 0.4s ease, transform 0.4s ease, margin 0.4s ease, padding 0.4s ease, height 0.4s ease';
                    flash.style.opacity = '0';
                    flash.style.transform = 'translateY(-12px)';
                    
                    // Slide up & collapse height
                    setTimeout(() => {
                        flash.style.height = '0';
                        flash.style.padding = '0';
                        flash.style.margin = '0';
                        flash.style.border = 'none';
                        
                        // Clean up fully
                        setTimeout(() => {
                            flash.remove();
                            if (flashContainer.children.length === 0) {
                                flashContainer.remove();
                            }
                        }, 400);
                    }, 300);
                }, index * 150); // Stagger removal
            });
        }, 4000); // Wait 4 seconds before triggering auto-close
    }
});

// Create and show a gorgeous floating toast notification on-the-fly
function showToastMessage(message, type = 'info') {
    // Remove existing toast if present
    const existing = document.getElementById('globalToast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'globalToast';
    toast.style.position = 'fixed';
    toast.style.top = '24px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%) translateY(-20px)';
    toast.style.backgroundColor = 'var(--bg-card)';
    toast.style.border = '1px solid ' + (type === 'success' ? 'var(--primary)' : 'var(--border-color)');
    toast.style.color = 'var(--text-white)';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = 'var(--radius-md)';
    toast.style.fontSize = '13px';
    toast.style.fontWeight = '600';
    toast.style.boxShadow = 'var(--shadow-premium)';
    toast.style.zIndex = '9999';
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    toast.style.gap = '8px';
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease, transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.15)';

    // Choose SVG icon
    let iconSvg = '';
    if (type === 'success') {
        iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    } else {
        iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `${iconSvg}<span>${message}</span>`;
    document.body.appendChild(toast);

    // Trigger animation frame to show
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(-50%) translateY(0)';
    });

    // Auto-dismiss toast
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(-50%) translateY(-15px)';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 2800);
}
