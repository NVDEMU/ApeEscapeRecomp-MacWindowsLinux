#include <stdint.h>

/* The PGXP projection fixture contains ordinary RAM only; no optional
 * extended GPU-DMA aperture is allocated by this standalone test. */
int psx_mod_gpu_dma_memory_contains(uint32_t address, uint32_t bytes) {
  (void)address;
  (void)bytes;
  return 0;
}
