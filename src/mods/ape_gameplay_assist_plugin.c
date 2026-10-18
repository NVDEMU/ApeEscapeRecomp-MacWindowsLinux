#include "mod_plugins.h"

#include <stdint.h>
#include <stddef.h>

/*
 * Optional North American Ape Escape gameplay assists.
 *
 * The writable RAM locations below match documented SCUS-94423 cheat-code
 * values. Keep the writes in active gameplay only: menu, title, save/load and
 * attract/demo states should retain their stock behavior. The catalog keeps
 * each assist as a separate default-off feature.
 */
static const uint32_t APE_TRANSITION_PHASE_ADDRESS = 0x800F447Cu;
static const uint8_t APE_TRANSITION_PLAYING = 0x03u;

static const uint32_t APE_LIVES_ADDRESS = 0x800F448Cu;
static const uint32_t APE_HEALTH_ADDRESS = 0x800EC2C8u;
static const uint32_t APE_AIR_ADDRESS = 0x800F4DC8u;
static const uint32_t APE_UNLOCKED_GADGETS_ADDRESS = 0x800F51C4u;

/*
 * Published SCUS-94423 cheat references identify these RAM bytes as per-stage
 * completion/status records. Value 2 is documented as 100% complete. Value 1
 * is an inferred unlocked-but-not-completed state, so this feature is marked
 * experimental until it is verified in-game on a backed-up save. Only zero
 * entries are changed: completed or otherwise nonzero states are preserved.
 *
 * Gaps are intentional; these are the documented playable-stage records, not
 * a blanket write across the surrounding RAM range.
 */
static const uint32_t APE_STAGE_STATUS_ADDRESSES[] = {
    0x800DFC71u, /* Fossil Field */
    0x800DFC72u, /* Primordial Ooze */
    0x800DFC73u, /* Molten Lava */
    0x800DFC74u, /* Thick Jungle */
    0x800DFC75u, /* Dark Ruins */
    0x800DFC76u, /* Cryptic Relics */
    0x800DFC77u, /* Stadium Attack */
    0x800DFC78u, /* Crabby Beach */
    0x800DFC79u, /* Coral Cave */
    0x800DFC7Au, /* Dexter's Island */
    0x800DFC7Bu, /* Snowy Mammoth */
    0x800DFC7Cu, /* Frosty Retreat */
    0x800DFC7Du, /* Hot Springs */
    0x800DFC7Eu, /* Gladiator Attack */
    0x800DFC7Fu, /* Sushi Temple */
    0x800DFC80u, /* Wabi Sabi Wall */
    0x800DFC81u, /* Crumbling Castle */
    0x800DFC84u, /* City Park */
    0x800DFC85u, /* Spectar's Factory */
    0x800DFC86u, /* TV Tower */
    0x800DFC88u, /* Monkey Madness */
    0x800DFC8Eu  /* Peak Point Matrix */
};

static int ape_assist_is_active(void) {
    return psx_mod_game_started() &&
           psx_mod_read_byte(APE_TRANSITION_PHASE_ADDRESS) ==
               APE_TRANSITION_PLAYING;
}

static void ape_assist_infinite_lives(void) {
    if (!ape_assist_is_active())
        return;
    psx_mod_write_half(APE_LIVES_ADDRESS, 100u);
}

static void ape_assist_infinite_health(void) {
    if (!ape_assist_is_active())
        return;
    psx_mod_write_half(APE_HEALTH_ADDRESS, 5u);
}

static void ape_assist_infinite_air(void) {
    if (!ape_assist_is_active())
        return;
    psx_mod_write_half(APE_AIR_ADDRESS, 0x0258u);
}

static void ape_assist_all_gadgets(void) {
    if (!ape_assist_is_active())
        return;

    /* A bit per gadget. Write only if needed to avoid unnecessary RAM writes. */
    if (psx_mod_read_byte(APE_UNLOCKED_GADGETS_ADDRESS) != 0xFFu)
        psx_mod_write_byte(APE_UNLOCKED_GADGETS_ADDRESS, 0xFFu);
}

static void ape_assist_unlock_all_stages(void) {
    size_t i;

    if (!ape_assist_is_active())
        return;

    for (i = 0; i < sizeof(APE_STAGE_STATUS_ADDRESSES) /
                        sizeof(APE_STAGE_STATUS_ADDRESSES[0]); ++i) {
        const uint32_t address = APE_STAGE_STATUS_ADDRESSES[i];
        const uint8_t status = psx_mod_read_byte(address);

        /*
         * Never replace a nonzero value: the published 100%-complete code
         * uses 2, and other nonzero status values may carry player progress.
         * Value 1 is the unlock-only hypothesis to validate in-game.
         */
        if (status == 0u)
            psx_mod_write_byte(address, 1u);
    }
}

PSX_MOD_CONSTRUCTOR(ape_register_gameplay_assist_plugins) {
    (void)psx_mod_register_vblank_plugin(
        "ape.assist.infinite-lives", ape_assist_infinite_lives);
    (void)psx_mod_register_vblank_plugin(
        "ape.assist.infinite-health", ape_assist_infinite_health);
    (void)psx_mod_register_vblank_plugin(
        "ape.assist.infinite-air", ape_assist_infinite_air);
    (void)psx_mod_register_vblank_plugin(
        "ape.assist.all-gadgets", ape_assist_all_gadgets);
    (void)psx_mod_register_vblank_plugin(
        "ape.assist.unlock-all-stages", ape_assist_unlock_all_stages);
}
