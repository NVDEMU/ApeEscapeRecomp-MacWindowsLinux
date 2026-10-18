/* APE_ESCAPE_NEW_FEATURES_HELPER
 * Launcher-side features. Challenge data and profile data stay in the user's
 * data directory; no game RAM is modified by these tools.
 */
static std::string s_ape_daily_status;
static std::string s_ape_save_protection_status;
static std::string s_ape_toolkit_status;
static std::string s_ape_setup_doctor_status;
static std::string s_ape_controller_test_status;
static std::string s_ape_update_center_status;
/* These helpers are injected before the framework's mod-renderer definitions. */
static int s_ape_mod_filter = 0;
static void mod_note_error(LauncherModel* m);
static std::string s_ape_selected_save_backup;
static int s_ape_save_backup_retention = 20;
static bool s_ape_save_backup_retention_loaded = false;
static SDL_Gamepad* s_ape_controller_test_gamepad = nullptr;
static SDL_JoystickID s_ape_controller_test_gamepad_id = 0;
static int s_ape_stage_selected = 0;
static bool s_ape_stage_show_tips = true;

static bool ape_escape_copy_regular_tree(const std::filesystem::path& source,
                                         const std::filesystem::path& target,
                                         bool skip_save_protection = false) {
    std::error_code ec;
    if (!std::filesystem::exists(source, ec)) return !ec;
    if (ec || !std::filesystem::is_directory(source, ec) || ec) return false;
    std::filesystem::create_directories(target, ec);
    if (ec) return false;
    for (std::filesystem::directory_iterator it(source, ec), end; !ec && it != end; it.increment(ec)) {
        const auto status = it->symlink_status(ec);
        if (ec) return false;
        if (std::filesystem::is_symlink(status)) continue;
        const auto name = it->path().filename();
        if (skip_save_protection && name == "save-protection" &&
            std::filesystem::is_directory(status)) continue;
        const auto destination = target / name;
        if (std::filesystem::is_directory(status)) {
            if (!ape_escape_copy_regular_tree(it->path(), destination, false)) return false;
        } else if (std::filesystem::is_regular_file(status)) {
            std::filesystem::create_directories(destination.parent_path(), ec);
            if (ec) return false;
            std::filesystem::copy_file(it->path(), destination,
                std::filesystem::copy_options::overwrite_existing, ec);
            if (ec) return false;
        }
    }
    return !ec;
}

static std::string ape_escape_backup_timestamp() {
    const std::time_t now = std::time(nullptr);
    const std::tm* local = std::localtime(&now);
    char stamp[32] = {};
    if (!local || std::strftime(stamp, sizeof(stamp), "%Y%m%d-%H%M%S", local) == 0)
        return {};
    return stamp;
}

static std::filesystem::path ape_escape_latest_save_backup() {
    const auto root = ape_escape_data_directory() / "save-protection";
    std::error_code ec;
    if (!std::filesystem::is_directory(root, ec) || ec) return {};
    std::filesystem::path latest;
    std::string latest_name;
    for (std::filesystem::directory_iterator it(root, ec), end; !ec && it != end; it.increment(ec)) {
        if (!it->is_directory(ec) || ec) { ec.clear(); continue; }
        const std::string name = it->path().filename().string();
        if (name.rfind("backup-", 0) != 0) continue;
        ec.clear();
        if (!std::filesystem::is_regular_file(it->path() / "BACKUP_INFO.txt", ec) || ec) {
            ec.clear();
            continue;
        }
        if (name > latest_name) {
            latest_name = name;
            latest = it->path();
        }
    }
    return latest;
}

static int ape_escape_clamp_backup_retention(int value) {
    return std::max(5, std::min(50, value));
}

static void ape_escape_load_backup_retention() {
    if (s_ape_save_backup_retention_loaded) return;
    s_ape_save_backup_retention_loaded = true;
    std::ifstream input(ape_escape_data_directory() / "save-protection-retention.txt");
    int value = 20;
    if (input >> value) s_ape_save_backup_retention = ape_escape_clamp_backup_retention(value);
    else s_ape_save_backup_retention = 20;
}

static void ape_escape_store_backup_retention() {
    std::error_code ec;
    std::filesystem::create_directories(ape_escape_data_directory(), ec);
    if (ec) return;
    std::ofstream output(ape_escape_data_directory() / "save-protection-retention.txt", std::ios::trunc);
    if (output) output << ape_escape_clamp_backup_retention(s_ape_save_backup_retention) << "\n";
}

static void ape_escape_prune_save_backups(int retention) {
    const size_t keep = static_cast<size_t>(ape_escape_clamp_backup_retention(retention));
    const auto root = ape_escape_data_directory() / "save-protection";
    std::error_code ec;
    for (;;) {
        std::map<std::string, std::filesystem::path> backups;
        ec.clear();
        if (!std::filesystem::is_directory(root, ec) || ec) return;
        for (std::filesystem::directory_iterator it(root, ec), end; !ec && it != end; it.increment(ec)) {
            const std::string name = it->path().filename().string();
            if (name.rfind("backup-", 0) != 0) continue;
            ec.clear();
            if (!it->is_directory(ec) || ec) { ec.clear(); continue; }
            if (std::filesystem::is_regular_file(it->path() / "BACKUP_INFO.txt", ec) && !ec)
                backups.emplace(name, it->path());
            ec.clear();
        }
        if (ec || backups.size() <= keep) return;
        ec.clear();
        std::filesystem::remove_all(backups.begin()->second, ec);
        if (ec) return;
    }
}

static std::filesystem::path ape_escape_create_save_backup(bool prune_after = true) {
    ape_escape_load_backup_retention();
    const auto data = ape_escape_data_directory();
    const auto app = ape_escape_application_directory();
    const auto root = data / "save-protection";
    std::error_code ec;
    std::filesystem::create_directories(root, ec);
    if (ec) return {};
    const std::string stamp = ape_escape_backup_timestamp();
    if (stamp.empty()) return {};
    std::string suffix;
    std::filesystem::path target;
    for (unsigned attempt = 0; attempt < 100; ++attempt) {
        suffix = attempt == 0 ? "" : "-" + std::to_string(attempt);
        target = root / ("backup-" + stamp + suffix);
        ec.clear();
        if (!std::filesystem::exists(target, ec) && !ec) break;
        target.clear();
    }
    if (target.empty()) return {};
    const auto pending = root / (".pending-" + stamp + suffix);
    std::filesystem::remove_all(pending, ec);
    ec.clear();
    std::filesystem::create_directories(pending, ec);
    if (ec) return {};
    const bool user_ok = ape_escape_copy_regular_tree(data, pending / "user-data", true);
    const bool saves_ok = ape_escape_copy_regular_tree(app / "saves", pending / "app-saves", false);
    if (!user_ok || !saves_ok) {
        std::filesystem::remove_all(pending, ec);
        return {};
    }
    std::ofstream info(pending / "BACKUP_INFO.txt", std::ios::trunc);
    if (!info) {
        std::filesystem::remove_all(pending, ec);
        return {};
    }
    info << "Ape Escape Recompiled - Enhanced Edition save protection backup\n"
         << "Created: " << stamp << "\n"
         << "Contents: user-writable application data and the install-local saves/ folder when present\n"
         << "Restore mode: merges snapshot files; files not present in the snapshot are not deleted.\n";
    info.close();
    if (!info) {
        std::filesystem::remove_all(pending, ec);
        return {};
    }
    std::filesystem::rename(pending, target, ec);
    if (ec) {
        std::filesystem::remove_all(pending, ec);
        return {};
    }
    if (prune_after) ape_escape_prune_save_backups(s_ape_save_backup_retention);
    return target;
}

static bool ape_escape_restore_save_backup(const std::filesystem::path& snapshot) {
    if (snapshot.empty() ||
        !std::filesystem::is_regular_file(snapshot / "BACKUP_INFO.txt")) return false;
    /* Preserve the current state before applying an older snapshot. */
    /* Do not prune yet: the selected historical snapshot could be the oldest
     * one, and must remain available until its contents have been restored. */
    if (ape_escape_create_save_backup(false).empty()) return false;
    const bool data_ok = ape_escape_copy_regular_tree(
        snapshot / "user-data", ape_escape_data_directory(), false);
    const bool saves_ok = ape_escape_copy_regular_tree(
        snapshot / "app-saves", ape_escape_application_directory() / "saves", false);
    if (data_ok && saves_ok)
        ape_escape_prune_save_backups(s_ape_save_backup_retention);
    return data_ok && saves_ok;
}

/* SAVE PROTECTION CENTER is explicit/manual. Restore is confirmed in the UI,
 * first creates a safety backup, merges files, and never deletes newer files. */
static std::vector<std::filesystem::path> ape_escape_list_save_backups() {
    const auto root = ape_escape_data_directory() / "save-protection";
    std::vector<std::filesystem::path> backups;
    std::error_code ec;
    if (!std::filesystem::is_directory(root, ec) || ec) return backups;
    for (std::filesystem::directory_iterator it(root, ec), end; !ec && it != end; it.increment(ec)) {
        if (!it->is_directory(ec) || ec) { ec.clear(); continue; }
        const auto path = it->path();
        if (path.filename().string().rfind("backup-", 0) != 0) continue;
        ec.clear();
        if (std::filesystem::is_regular_file(path / "BACKUP_INFO.txt", ec) && !ec)
            backups.push_back(path);
        ec.clear();
    }
    std::sort(backups.begin(), backups.end(),
        [](const std::filesystem::path& a, const std::filesystem::path& b) {
            return a.filename().string() > b.filename().string();
        });
    return backups;
}

static bool ape_escape_export_save_backup(const std::filesystem::path& snapshot,
                                           const std::filesystem::path& destination_dir,
                                           std::filesystem::path* exported_path) {
    if (exported_path) exported_path->clear();
    std::error_code ec;
    if (snapshot.empty() ||
        !std::filesystem::is_regular_file(snapshot / "BACKUP_INFO.txt", ec) || ec ||
        !std::filesystem::is_directory(destination_dir, ec) || ec)
        return false;

    std::filesystem::path target;
    for (unsigned attempt = 0; attempt < 100; ++attempt) {
        std::string suffix = "-exported";
        if (attempt) suffix += "-" + std::to_string(attempt);
        target = destination_dir / (snapshot.filename().string() + suffix);
        ec.clear();
        if (!std::filesystem::exists(target, ec) && !ec) break;
        target.clear();
    }
    if (target.empty()) return false;

    const std::string source_normalized = snapshot.lexically_normal().string();
    const std::string target_normalized = target.lexically_normal().string();
    const std::string source_prefix =
        source_normalized + static_cast<char>(std::filesystem::path::preferred_separator); /* APE_ESCAPE_WINDOWS_PATH_SEPARATOR_FIX */
    if (target_normalized == source_normalized ||
        target_normalized.rfind(source_prefix, 0) == 0)
        return false;  // Never try to copy a backup into itself.

    if (!ape_escape_copy_regular_tree(snapshot, target, false)) {
        std::filesystem::remove_all(target, ec);
        return false;
    }
    if (exported_path) *exported_path = target;
    return true;
}

/* SAVE PROTECTION CENTER is explicit/manual. Restore is confirmed in the UI,
 * first creates a safety backup, merges files, and never deletes absent files. */
static void ape_escape_draw_save_protection_center(LauncherModel* m,
                                                    const LauncherTheme& th,
                                                    float button_w, float gap) {
    ape_escape_load_backup_retention();
    ImGui::Spacing();
    ImGui::Separator();
    ImGui::TextColored(col(th.accent2), "SAVE PROTECTION CENTER");
    ImGui::TextWrapped("Create, browse, export, and restore snapshots. Restore makes a safety backup first and never deletes files absent from the selected snapshot.");

    const auto backups = ape_escape_list_save_backups();
    if (backups.empty()) {
        s_ape_selected_save_backup.clear();
        ImGui::TextDisabled("No valid backup exists yet. Create one before restoring.");
    } else {
        bool selected_found = false;
        for (const auto& path : backups) {
            const std::string name = path.filename().string();
            const bool selected = (s_ape_selected_save_backup == name);
            if (selected) selected_found = true;
        }
        if (!selected_found) s_ape_selected_save_backup = backups.front().filename().string();

        ImGui::TextUnformatted("Backup history");
        if (ImGui::BeginChild("##save_backup_history", ImVec2(0, px(108.0f)), ImGuiChildFlags_Borders)) {
            for (const auto& path : backups) {
                const std::string name = path.filename().string();
                const std::string label = name + (name == s_ape_selected_save_backup ? "  [selected]" : "");
                if (ImGui::Selectable(label.c_str(), name == s_ape_selected_save_backup))
                    s_ape_selected_save_backup = name;
            }
        }
        ImGui::EndChild();
    }

    std::filesystem::path selected_backup;
    for (const auto& path : backups) {
        if (path.filename().string() == s_ape_selected_save_backup) {
            selected_backup = path;
            break;
        }
    }

    if (ImGui::Button("Create Backup Now", ImVec2(button_w, px(34.0f)))) {
        const auto created = ape_escape_create_save_backup();
        s_ape_save_protection_status = created.empty()
            ? "Backup failed. Check disk permissions and available storage."
            : "Backup created: " + created.filename().string();
    }

    ImGui::SameLine(0, gap);
    ImGui::BeginDisabled(selected_backup.empty());
    if (ImGui::Button("Restore Selected", ImVec2(button_w, px(34.0f))))
        ImGui::OpenPopup("Confirm Save Restore");
    if (ImGui::Button("Export Selected", ImVec2(button_w, px(34.0f)))) {
        const auto export_source = selected_backup;
        ui_pick_folder(m, "Export Backup To Folder", [export_source](const char* destination) {
            if (!destination || !destination[0]) return;
            std::filesystem::path output_path;
            const bool ok = ape_escape_export_save_backup(
                export_source, std::filesystem::path(destination), &output_path);
            s_ape_save_protection_status = ok
                ? "Backup exported to: " + output_path.string()
                : "Export failed. Choose a different writable destination folder.";
        });
    }
    ImGui::EndDisabled();

    if (ImGui::BeginPopupModal("Confirm Save Restore", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::TextWrapped("Restore %s? The current data will first be saved in a separate safety snapshot. Matching files will then be overwritten; newer files will not be deleted.",
                          selected_backup.empty() ? "(no backup selected)" : selected_backup.filename().string().c_str());
        ImGui::BeginDisabled(selected_backup.empty());
        if (ImGui::Button("Create Safety Backup and Restore", ImVec2(px(270.0f), px(34.0f)))) {
            s_ape_save_protection_status = ape_escape_restore_save_backup(selected_backup)
                ? "Restore completed. A pre-restore safety snapshot was saved."
                : "Restore failed. Check permissions and backup integrity.";
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndDisabled();
        ImGui::SameLine();
        if (ImGui::Button("Cancel", ImVec2(px(100.0f), px(34.0f))))
            ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    const int old_retention = s_ape_save_backup_retention;
    if (ImGui::SliderInt("Keep backups", &s_ape_save_backup_retention, 5, 50)) {
        s_ape_save_backup_retention = ape_escape_clamp_backup_retention(s_ape_save_backup_retention);
        if (s_ape_save_backup_retention != old_retention) {
            ape_escape_store_backup_retention();
            s_ape_save_protection_status = "Retention saved. The new limit is applied after the next successful backup.";
        }
    }
    ImGui::TextDisabled("Keep between 5 and 50 snapshots. Existing backups are not removed just by changing this setting.");
    if (!s_ape_save_protection_status.empty())
        ImGui::TextWrapped("%s", s_ape_save_protection_status.c_str());
}

/* A date-only deterministic challenge seed: no network, no game RNG, no uploads. */
struct ApeEscapeDailyChallenge {
    std::string date, code, first, second;
};
static std::map<std::string, bool> ape_escape_load_daily_history() {
    std::map<std::string, bool> history;
    std::ifstream in(ape_escape_data_directory() / "ape_escape_daily_challenges.tsv");
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream row(line);
        std::string date, code, complete;
        if (std::getline(row, date, '\t') && std::getline(row, code, '\t') &&
            std::getline(row, complete) && !date.empty())
            history[date] = complete == "1";
    }
    return history;
}
static bool ape_escape_save_daily_history(const std::map<std::string, bool>& history) {
    const auto path = ape_escape_data_directory() / "ape_escape_daily_challenges.tsv";
    std::ofstream out(path, std::ios::trunc);
    if (!out) return false;
    out << "# date<TAB>daily-code<TAB>manually-marked-complete\n";
    for (const auto& record : history)
        out << record.first << '\t' << "AE-" << record.first << '\t'
            << (record.second ? "1" : "0") << '\n';
    out.close();
    return static_cast<bool>(out);
}
static uint32_t ape_escape_daily_next(uint32_t* state) {
    *state ^= *state << 13u;
    *state ^= *state >> 17u;
    *state ^= *state << 5u;
    if (*state == 0u) *state = 0xA341316Cu;
    return *state;
}
static std::string ape_escape_daily_rule(unsigned kind, uint32_t* state) {
    if (kind == 0u) {
        const unsigned minutes[] = {3u, 5u, 10u};
        return "Timed Monkey Hunt — " + std::to_string(minutes[ape_escape_daily_next(state) % 3u]) + " minutes";
    }
    if (kind == 1u) return "No-Damage Run — finish without losing health";
    const unsigned lives[] = {1u, 3u, 5u};
    return "Limited Lives — " + std::to_string(lives[ape_escape_daily_next(state) % 3u]) + " starting lives";
}
static ApeEscapeDailyChallenge ape_escape_today_challenge() {
    const std::time_t now = std::time(nullptr);
    const std::tm* local = std::localtime(&now);
    std::tm date_parts{};
    if (local) date_parts = *local;
    char date[16] = {};
    std::strftime(date, sizeof(date), "%Y-%m-%d", &date_parts);
    const uint32_t numeric_date = static_cast<uint32_t>((date_parts.tm_year + 1900) * 10000 +
        (date_parts.tm_mon + 1) * 100 + date_parts.tm_mday);
    uint32_t state = numeric_date ^ 0x9E3779B9u;
    if (!state) state = 0xA341316Cu;
    const unsigned first_kind = ape_escape_daily_next(&state) % 3u;
    unsigned second_kind = ape_escape_daily_next(&state) % 3u;
    if (second_kind == first_kind) second_kind = (second_kind + 1u) % 3u;
    const uint32_t code_value = ape_escape_daily_next(&state) & 0xFFFFu;
    char code[40] = {};
    std::snprintf(code, sizeof(code), "AE-%04d%02d%02d-%04X",
        date_parts.tm_year + 1900, date_parts.tm_mon + 1, date_parts.tm_mday,
        static_cast<unsigned>(code_value));
    return {date, code, ape_escape_daily_rule(first_kind, &state),
            ape_escape_daily_rule(second_kind, &state)};
}
static void ape_escape_draw_daily_challenge(LauncherModel*, const LauncherTheme& th) {
    const auto challenge = ape_escape_today_challenge();
    auto history = ape_escape_load_daily_history();
    const bool completed = history[challenge.date];
    ImGui::TextColored(col(th.accent2), "DAILY CHALLENGE");
    ImGui::TextWrapped("A reproducible challenge generated from your local calendar date. Players using the same date and version receive the same rules.");
    ImGui::Separator();
    ImGui::Text("Date: %s", challenge.date.c_str());
    ImGui::TextColored(col(th.accent), "Challenge code: %s", challenge.code.c_str());
    ImGui::Spacing();
    ImGui::BulletText("Primary rule: %s", challenge.first.c_str());
    ImGui::BulletText("Bonus rule: %s", challenge.second.c_str());
    ImGui::TextDisabled("Enable matching Challenge Pack features in Mods yourself. Rules are not auto-enabled, gameplay results are not verified, and no scores are uploaded.");
    if (ImGui::Button("Copy Challenge Code", ImVec2(px(190.0f), px(32.0f)))) {
        ImGui::SetClipboardText(challenge.code.c_str());
        s_ape_daily_status = "Challenge code copied.";
    }
    ImGui::SameLine();
    if (!completed && ImGui::Button("Mark Complete", ImVec2(px(160.0f), px(32.0f)))) {
        history[challenge.date] = true;
        s_ape_daily_status = ape_escape_save_daily_history(history)
            ? "Completion recorded locally. Results are self-reported."
            : "Could not write the local challenge history.";
    } else if (completed && ImGui::Button("Undo Completion", ImVec2(px(160.0f), px(32.0f)))) {
        history[challenge.date] = false;
        s_ape_daily_status = ape_escape_save_daily_history(history)
            ? "Completion mark removed."
            : "Could not update the local challenge history.";
    }
    if (!s_ape_daily_status.empty()) ImGui::TextWrapped("%s", s_ape_daily_status.c_str());
    std::size_t completed_count = 0;
    for (const auto& item : history) if (item.second) ++completed_count;
    ImGui::Text("Recorded completed challenge dates: %u", static_cast<unsigned>(completed_count));
}

static const char* ape_escape_stage_tip(int id) {
    switch (id) {
        case 0: return "Open routes reward decisive pursuit. Observe the monkey's reaction, then close distance before switching to your capture gadget.";
        case 1: return "Plan around the environment before chasing an alerted target. A short, safe route is often better than blindly following a fleeing monkey.";
        case 2: return "Prioritize safe footing near environmental hazards. Check your direction before committing to a long chase.";
        case 10: return "Use the Radar when vegetation or terrain hides a target. Reposition before changing to a slower capture tool.";
        case 11: return "Check side paths and corners before leaving an area. Avoid letting an alerted monkey pull you away from unexplored routes.";
        case 12: return "Scout the nearby route before pursuing. If a monkey gains distance, use the Radar to reacquire it rather than guessing.";
        case 20: return "Open areas can favor quick pursuit. Keep control near edges and check the path ahead before committing to a chase.";
        case 21: return "In enclosed routes, make room to turn before using movement gadgets. Check nearby side passages when a target leaves view.";
        case 22: return "Work through the area in a deliberate loop to reduce backtracking. Check the Radar for targets you may have passed.";
        case 30: return "Keep a clear escape route during pursuit. If terrain blocks your view, pause and reacquire the target with the Radar.";
        case 31: return "Plan turns before building speed and avoid chasing blindly around corners. Re-check the surrounding route after a capture.";
        case 32: return "Watch the environment while pursuing monkeys. If the direct path is risky, reposition instead of continuing at full speed.";
        case 40: return "Use controlled approaches in narrow passages. Switch gadgets before a chase when possible to avoid losing time on menus.";
        case 41: return "Pay attention to changes in elevation and route layout. Reposition before using gadgets that need a clear path.";
        case 42: return "Check adjacent routes and keep track of your return path. A quick Radar check can prevent unnecessary backtracking.";
        case 50: return "Sweep the area in sections and check beyond your current line of sight. Keep track of branches you have not explored.";
        case 51: return "Treat machinery and environmental hazards as part of the route. Scout a safe approach before pursuing a fleeing monkey.";
        case 52: return "Look for elevation changes and safe places to turn around. Keep an eye on the Radar when a target leaves the screen.";
        case 60: return "Prepare your gadget loadout before starting, then clear the stage methodically. This is a general briefing, not a verified boss walkthrough.";
        default: return "Scout the route, check the Radar when a monkey leaves view, and switch gadgets before a long chase. These are general tips, not a live map.";
    }
}
static void ape_escape_draw_stage_guide(LauncherModel*, const LauncherTheme& th) {
    ape_escape_load_monke_catalog();
    std::map<int, std::string> stages;
    for (const auto& entry : s_ape_monke_entries) stages.emplace(entry.stage, entry.stage_name);
    if (stages.empty()) {
        ImGui::TextWrapped("Stage cards could not load because assets/monkepedia.tsv is missing.");
        return;
    }
    if (stages.find(s_ape_stage_selected) == stages.end()) s_ape_stage_selected = stages.begin()->first;
    ImGui::TextColored(col(th.accent2), "STAGE KNOWLEDGE CARDS");
    ImGui::TextWrapped("Stage briefings use the project's North-American monkey roster. Tips are general guidance, not live gameplay telemetry.");
    ImGui::BeginChild("ape_stage_card_picker", ImVec2(0, px(170.0f)), true);
    for (const auto& stage : stages) {
        const auto count = static_cast<unsigned>(std::count_if(
            s_ape_monke_entries.begin(), s_ape_monke_entries.end(),
            [&stage](const ApeMonkeEntry& entry) { return entry.stage == stage.first; }));
        const std::string label = stage.second + "  (" + std::to_string(count) + " listed monkeys)##stage_" + std::to_string(stage.first);
        if (ImGui::Selectable(label.c_str(), s_ape_stage_selected == stage.first))
            s_ape_stage_selected = stage.first;
    }
    ImGui::EndChild();
    ImGui::Spacing();
    ImGui::Separator();
    ImGui::TextColored(col(th.accent), "%s", stages[s_ape_stage_selected].c_str());
    const auto roster_count = static_cast<unsigned>(std::count_if(
        s_ape_monke_entries.begin(), s_ape_monke_entries.end(),
        [](const ApeMonkeEntry& entry) { return entry.stage == s_ape_stage_selected; }));
    ImGui::Text("Source-backed roster: %u listed monkeys", roster_count);
    ImGui::TextWrapped("Objective: capture the stage's monkeys and use the game's own completion indicators to confirm progress.");
    if (s_ape_stage_show_tips) ImGui::TextWrapped("Field note: %s", ape_escape_stage_tip(s_ape_stage_selected));
    ImGui::Checkbox("Show general gameplay tips", &s_ape_stage_show_tips);
    const auto found = std::find_if(s_ape_monke_entries.begin(), s_ape_monke_entries.end(),
        [](const ApeMonkeEntry& entry) { return entry.stage == s_ape_stage_selected; });
    if (found != s_ape_monke_entries.end() && !found->source_url.empty()) {
        ImGui::TextWrapped("Roster reference: %s", found->source_url.c_str());
        if (ImGui::Button("Open Roster Source", ImVec2(px(190.0f), px(32.0f)))) {
            if (!SDL_OpenURL(found->source_url.c_str()))
                s_ape_toolkit_status = "Could not open the stage's roster reference.";
        }
    }
}

static const char APE_ESCAPE_EXAMPLE_PLUGIN[] = R"APE_PLUGIN(#include "mod_plugins.h"
#include <stdint.h>

/* Read-only starter. Verify address semantics against the current game build. */
static void example_vblank(void) {
    if (!psx_mod_game_started()) return;
    const uint16_t observed_word = psx_mod_read_half(0x800F4490u);
    (void)observed_word;
}

PSX_MOD_CONSTRUCTOR(register_example_plugin) {
    (void)psx_mod_register_vblank_plugin("example.timer-observer", example_vblank);
}
)APE_PLUGIN";
static void ape_escape_draw_mod_toolkit(LauncherModel*, const LauncherTheme& th) {
    ImGui::TextColored(col(th.accent2), "MOD DEVELOPER TOOLKIT");
    ImGui::TextWrapped("Start from the documented project API and a read-only observer. Undocumented memory writes can break game state or softlock stages.");
    ImGui::Separator();
    ImGui::BulletText("Use a unique plugin ID and keep every feature disabled by default.");
    ImGui::BulletText("Guard callbacks to the correct gameplay phase and clear transient state at stage transitions.");
    ImGui::BulletText("Record evidence for RAM mappings. Compilation alone does not validate behavior in-game.");
    ImGui::BulletText("Keep user data separate from the app install and test on clean saves.");
    if (ImGui::Button("Copy Minimal Plugin Template", ImVec2(px(230.0f), px(34.0f)))) {
        ImGui::SetClipboardText(APE_ESCAPE_EXAMPLE_PLUGIN);
        s_ape_toolkit_status = "A read-only example plugin was copied to the clipboard.";
    }
    if (ImGui::Button("Open Mod Developer Documentation", ImVec2(px(260.0f), px(34.0f)))) {
        if (SDL_OpenURL("https://github.com/NVDEMU/ApeEscapeRecomp-MacWindowsLinux/blob/master/docs/MOD_DEVELOPER_TOOLKIT.md"))
            s_ape_toolkit_status = "Opened the project mod-development documentation.";
        else
            s_ape_toolkit_status = "Could not open the documentation URL.";
    }
    if (!s_ape_toolkit_status.empty()) ImGui::TextWrapped("%s", s_ape_toolkit_status.c_str());
}


/* MOD MANAGER OVERHAUL -------------------------------------------------------
 * s_ape_mod_filter and its prototypes are declared before the shared Mod page
 * uses them by apply_recomp_ui_update_patch.py. Filters affect visible rows;
 * presets call the provider's existing feature_enable callback so changes are
 * persisted by the same path as normal manual toggles.
 */
static bool ape_escape_mod_filter_matches(const RecompLauncherCModFeature& feature) {
    switch (s_ape_mod_filter) {
        case 1: return feature.enabled != 0;
        case 2: return feature.enabled == 0;
        case 3: return feature.channel == RECOMP_MOD_CHANNEL_EXPERIMENTAL;
        case 4: return feature.has_error != 0;
        default: return true;
    }
}

static bool ape_escape_mod_package_filter_matches(
    const RecompLauncherCModPackage& package,
    const RecompLauncherCModProvider* mods) {
    if (s_ape_mod_filter == 0) return true;
    if (!mods || !mods->feature_count || !mods->feature_get)
        return s_ape_mod_filter == 1 ? package.enabled != 0 :
               s_ape_mod_filter == 2 ? package.enabled == 0 :
               s_ape_mod_filter == 4 ? package.has_error != 0 : false;

    const int count = mods->feature_count(mods->ctx);
    bool has_features = false, any_enabled = false, any_experimental = false, any_error = package.has_error != 0;
    for (int i = 0; i < count; ++i) {
        RecompLauncherCModFeature feature{};
        if (!mods->feature_get(mods->ctx, i, &feature) ||
            std::strcmp(feature.package_id, package.id) != 0)
            continue;
        has_features = true;
        any_enabled = any_enabled || feature.enabled != 0;
        any_experimental = any_experimental ||
            feature.channel == RECOMP_MOD_CHANNEL_EXPERIMENTAL;
        any_error = any_error || feature.has_error != 0;
    }
    switch (s_ape_mod_filter) {
        case 1: return any_enabled || (!has_features && package.enabled != 0);
        case 2: return !any_enabled && (!has_features || package.enabled == 0);
        case 3: return any_experimental;
        case 4: return any_error;
        default: return true;
    }
}

static bool ape_escape_is_visual_mod(const RecompLauncherCModFeature& feature) {
    return std::strcmp(feature.package_id, "ape.enhancement.widescreen") == 0 ||
           std::strcmp(feature.package_id, "ape.enhancement.frame-smoothing") == 0 ||
           std::strcmp(feature.package_id, "psx.enhancement.pgxp") == 0;
}

static bool ape_escape_is_challenge_mod(const RecompLauncherCModFeature& feature) {
    if (std::strcmp(feature.package_id, "ape.enhancement.challenge-pack") != 0)
        return false;
    return std::strcmp(feature.id, "time-trial") == 0 ||
           std::strcmp(feature.id, "no-damage") == 0 ||
           std::strcmp(feature.id, "limited-lives") == 0;
}

static void ape_escape_apply_mod_preset(LauncherModel* m, int preset) {
    const auto* mods = m ? m->mods : nullptr;
    if (!mods || !mods->feature_count || !mods->feature_get || !mods->feature_enable) {
        if (m) std::snprintf(m->mod_status, sizeof(m->mod_status),
                             "This build does not expose editable mod features.");
        return;
    }
    int changed = 0;
    bool failed = false;
    const int count = mods->feature_count(mods->ctx);
    for (int i = 0; i < count; ++i) {
        RecompLauncherCModFeature feature{};
        if (!mods->feature_get(mods->ctx, i, &feature) ||
            !launcher_mod_feature_listed(mods, &feature))
            continue;
        bool target = false;
        if (preset == 0) {
            target = false;  // Original Experience: turn off all visible features.
        } else if (preset == 1) {
            target = ape_escape_is_visual_mod(feature);
        } else if (preset == 2) {
            target = ape_escape_is_challenge_mod(feature);
        }
        if ((feature.enabled != 0) == target) continue;
        if (mods->feature_enable(mods->ctx, feature.package_id, feature.id, target ? 1 : 0)) {
            ++changed;
        } else {
            failed = true;
        }
    }
    if (failed) {
        mod_note_error(m);
    } else {
        const char* name = preset == 0 ? "Original Experience" :
                           preset == 1 ? "Visual Enhancements" : "Challenge Run";
        std::snprintf(m->mod_status, sizeof(m->mod_status),
                      "%s preset applied (%d feature changes). Review selections before pressing PLAY.",
                      name, changed);
    }
}

static void ape_escape_draw_mod_manager_overhaul(LauncherModel* m, const LauncherTheme& th) {
    const auto* mods = m ? m->mods : nullptr;
    if (!m || !mods || !mods->feature_count || !mods->feature_get || !mods->feature_enable)
        return;

    ImGui::Separator();
    ImGui::TextColored(col(th.accent2), "MOD MANAGER TOOLS");
    static const char* filters[] = {"All features", "Enabled", "Disabled", "Experimental", "Needs attention"};
    ImGui::SetNextItemWidth(px(210.0f));
    ImGui::Combo("Filter", &s_ape_mod_filter, filters, IM_ARRAYSIZE(filters));
    ImGui::SameLine();
    ImGui::TextDisabled("Search below works together with this filter.");

    static int preset = 0;
    static const char* presets[] = {"Original Experience", "Visual Enhancements", "Challenge Run"};
    ImGui::SetNextItemWidth(px(220.0f));
    ImGui::Combo("Preset", &preset, presets, IM_ARRAYSIZE(presets));
    ImGui::SameLine();
    if (ImGui::Button("Apply Preset")) {
        ImGui::OpenPopup("Confirm Mod Preset");
    }
    if (ImGui::BeginPopupModal("Confirm Mod Preset", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::TextWrapped("Apply %s? This changes the enabled state of matching mod features. Changes are saved to the mod selection and take effect when you press PLAY.",
                          presets[preset]);
        if (preset == 0)
            ImGui::TextWrapped("Original Experience will disable every visible mod feature.");
        else if (preset == 1)
            ImGui::TextWrapped("Visual Enhancements enables widescreen, interpolated rendering, and PGXP. Other visible features are disabled.");
        else
            ImGui::TextWrapped("Challenge Run enables timed hunt, no-damage, and limited-lives rules. Other visible features are disabled; Nightmare Mode stays off.");
        if (ImGui::Button("Apply", ImVec2(px(120.0f), px(32.0f)))) {
            ape_escape_apply_mod_preset(m, preset);
            ImGui::CloseCurrentPopup();
        }
        ImGui::SameLine();
        if (ImGui::Button("Cancel", ImVec2(px(100.0f), px(32.0f))))
            ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }
}

/* SETUP DOCTOR -------------------------------------------------------------- */
struct ApeEscapeSetupDoctorResults {
    bool checked = false;
    bool disc_selected = false;
    bool disc_exists = false;
    bool disc_verified = false;
    bool bios_path_ok = true;
    bool data_writable = false;
    bool backup_exists = false;
    bool mod_error = false;
};

static ApeEscapeSetupDoctorResults s_ape_doctor_results;

static bool ape_escape_test_writable_directory(const std::filesystem::path& dir) {
    std::error_code ec;
    std::filesystem::create_directories(dir, ec);
    if (ec || !std::filesystem::is_directory(dir, ec) || ec) return false;
    for (int attempt = 0; attempt < 20; ++attempt) {
        const auto test_path = dir / (".ape-escape-doctor-write-check-" + std::to_string(attempt) + ".tmp");
        ec.clear();
        if (std::filesystem::exists(test_path, ec)) continue;
        std::ofstream output(test_path, std::ios::binary | std::ios::out);
        if (!output) return false;
        output << "temporary write check\n";
        output.close();
        const bool wrote = static_cast<bool>(output);
        ec.clear();
        std::filesystem::remove(test_path, ec);
        return wrote && !ec;
    }
    return false;
}

static void ape_escape_run_setup_doctor(LauncherModel* m) {
    s_ape_doctor_results = {};
    s_ape_doctor_results.checked = true;
    std::error_code ec;
    s_ape_doctor_results.disc_selected = m && m->rom_present && m->rom_full[0];
    s_ape_doctor_results.disc_exists = s_ape_doctor_results.disc_selected &&
        std::filesystem::is_regular_file(std::filesystem::path(m->rom_full), ec) && !ec;
    s_ape_doctor_results.disc_verified = s_ape_doctor_results.disc_exists &&
        launcher_model_rom_verified(m);
    s_ape_doctor_results.bios_path_ok = true;
    if (m && m->has_bios && m->s.bios_path[0]) {
        ec.clear();
        s_ape_doctor_results.bios_path_ok =
            std::filesystem::is_regular_file(std::filesystem::path(m->s.bios_path), ec) && !ec;
    }
    s_ape_doctor_results.data_writable =
        ape_escape_test_writable_directory(ape_escape_data_directory());
    s_ape_doctor_results.backup_exists = !ape_escape_latest_save_backup().empty();
    s_ape_doctor_results.mod_error = m && m->mod_status[0];
}

static void ape_escape_doctor_row(const LauncherTheme& th, const char* label,
                                  bool ok, const char* detail) {
    ImGui::TextColored(col(ok ? th.good : th.warn), "%s", ok ? "PASS" : "CHECK");
    ImGui::SameLine();
    ImGui::Text("%s", label);
    ImGui::SameLine();
    ImGui::TextColored(col(th.text_muted), "— %s", detail);
}

static std::string ape_escape_setup_doctor_report(LauncherModel* m) {
    if (!s_ape_doctor_results.checked) ape_escape_run_setup_doctor(m);
    std::ostringstream report;
    report << "Ape Escape Recompiled - Setup Doctor\n"
           << ape_escape_build_info() << "\n"
           << "Disc selected: " << (s_ape_doctor_results.disc_selected ? "yes" : "no") << "\n"
           << "Disc file exists: " << (s_ape_doctor_results.disc_exists ? "yes" : "no") << "\n"
           << "Disc verification: " << (s_ape_doctor_results.disc_verified ? "verified" : "not verified") << "\n"
           << "Selected BIOS path: " << (s_ape_doctor_results.bios_path_ok ? "valid or default" : "missing") << "\n"
           << "Application data writable: " << (s_ape_doctor_results.data_writable ? "yes" : "no") << "\n"
           << "Save backup exists: " << (s_ape_doctor_results.backup_exists ? "yes" : "no") << "\n"
           << "Mod status message present: " << ((m && m->mod_status[0]) ? "yes" : "no") << "\n";
    return report.str();
}

static void ape_escape_draw_setup_doctor(LauncherModel* m, const LauncherTheme& th) {
    if (!ImGui::CollapsingHeader("SETUP DOCTOR")) return;
    if (!s_ape_doctor_results.checked) ape_escape_run_setup_doctor(m);
    ImGui::TextWrapped("Quick checks for common launch and configuration problems. These checks do not modify game saves or silently reset settings.");
    ape_escape_doctor_row(th, "Game image", s_ape_doctor_results.disc_exists,
        !s_ape_doctor_results.disc_selected ? "none selected" :
        !s_ape_doctor_results.disc_exists ? "selected file is missing" : "file is accessible");
    ape_escape_doctor_row(th, "Disc identity", s_ape_doctor_results.disc_verified,
        s_ape_doctor_results.disc_verified ? "verified by this build" :
        s_ape_doctor_results.disc_exists ? "not verified; check the selected image" : "unavailable until a valid image is selected");
    ape_escape_doctor_row(th, "BIOS path", s_ape_doctor_results.bios_path_ok,
        s_ape_doctor_results.bios_path_ok ? "custom BIOS path is valid or default BIOS is selected" : "custom BIOS file is missing");
    ape_escape_doctor_row(th, "Application data", s_ape_doctor_results.data_writable,
        s_ape_doctor_results.data_writable ? "read/write check passed" : "cannot write to the app-data folder");
    ape_escape_doctor_row(th, "Save protection", s_ape_doctor_results.backup_exists,
        s_ape_doctor_results.backup_exists ? "a valid backup is available" : "no backup yet");
    if (s_ape_doctor_results.mod_error)
        ImGui::TextColored(col(th.warn), "Recent mod status: %s", m->mod_status);

    const float gap = px(8.0f);
    float w = (ImGui::GetContentRegionAvail().x - gap) * 0.5f;
    if (w < px(120.0f)) w = px(120.0f);
    if (ImGui::Button("Select / Repair Disc", ImVec2(w, px(32.0f)))) {
        ui_pick_file(m, "Select Ape Escape Disc Image",
            {"*.chd", "*.cue", "*.bin", "*.iso"}, "Ape Escape disc image",
            [m](const char* path) { if (path) launcher_model_set_rom(m, path); });
    }
    ImGui::SameLine(0, gap);
    if (ImGui::Button("Open Data Folder", ImVec2(w, px(32.0f))))
        ape_escape_open_folder(ape_escape_data_directory());
    if (ImGui::Button("Open Settings", ImVec2(w, px(32.0f))))
        launcher_model_set_view(m, LNG_VIEW_SETTINGS);
    ImGui::SameLine(0, gap);
    if (ImGui::Button("Run Checks Again", ImVec2(w, px(32.0f)))) {
        ape_escape_run_setup_doctor(m);
        s_ape_setup_doctor_status = "Setup checks refreshed.";
    }
    if (ImGui::Button("Copy Diagnostic Report", ImVec2(w, px(32.0f)))) {
        const std::string report = ape_escape_setup_doctor_report(m);
        ImGui::SetClipboardText(report.c_str());
        s_ape_setup_doctor_status = "Diagnostic report copied. Review it before sharing.";
    }
    if (!s_ape_setup_doctor_status.empty())
        ImGui::TextWrapped("%s", s_ape_setup_doctor_status.c_str());
}

/* CONTROLLER TEST LAB ------------------------------------------------------- */
static void ape_escape_draw_stick_test(const char* id, const char* label,
                                       float x, float y, const LauncherTheme& th) {
    ImGui::TextUnformatted(label);
    const float side = px(100.0f);
    ImGui::InvisibleButton(id, ImVec2(side, side));
    const ImVec2 minimum = ImGui::GetItemRectMin();
    const ImVec2 maximum = ImGui::GetItemRectMax();
    const ImVec2 center((minimum.x + maximum.x) * 0.5f, (minimum.y + maximum.y) * 0.5f);
    ImDrawList* draw = ImGui::GetWindowDrawList();
    draw->AddRect(minimum, maximum, ImGui::ColorConvertFloat4ToU32(col(th.border)), px(5.0f));
    draw->AddLine(ImVec2(center.x, minimum.y), ImVec2(center.x, maximum.y),
                  ImGui::ColorConvertFloat4ToU32(col(th.text_muted)));
    draw->AddLine(ImVec2(minimum.x, center.y), ImVec2(maximum.x, center.y),
                  ImGui::ColorConvertFloat4ToU32(col(th.text_muted)));
    const float radius = side * 0.42f;
    const ImVec2 dot(center.x + std::max(-1.0f, std::min(1.0f, x)) * radius,
                     center.y + std::max(-1.0f, std::min(1.0f, y)) * radius);
    draw->AddCircleFilled(dot, px(6.0f), ImGui::ColorConvertFloat4ToU32(col(th.accent)));
    draw->AddCircle(dot, px(6.0f), ImGui::ColorConvertFloat4ToU32(col(th.text)));
}

static void ape_escape_close_test_gamepad() {
    if (s_ape_controller_test_gamepad) {
        SDL_CloseGamepad(s_ape_controller_test_gamepad);
        s_ape_controller_test_gamepad = nullptr;
    }
    s_ape_controller_test_gamepad_id = 0;
}

static void ape_escape_draw_controller_test_lab(const LauncherTheme& th) {
    if (!ImGui::CollapsingHeader("CONTROLLER TEST LAB")) return;
    ImGui::TextWrapped("Move sticks, press buttons, and test rumble to confirm that SDL sees your controller. This page is diagnostic only and does not change your button mappings.");

    int count = 0;
    SDL_JoystickID* ids = SDL_GetGamepads(&count);
    if (!ids || count <= 0) {
        if (ids) SDL_free(ids);
        ape_escape_close_test_gamepad();
        ImGui::TextDisabled("No SDL gamepad detected. Connect a controller; this panel will detect it.");
        return;
    }

    bool selected_exists = false;
    for (int i = 0; i < count; ++i)
        if (ids[i] == s_ape_controller_test_gamepad_id) selected_exists = true;
    if (!selected_exists) {
        ape_escape_close_test_gamepad();
        s_ape_controller_test_gamepad_id = ids[0];
    }

    const char* current_name_raw = SDL_GetGamepadNameForID(s_ape_controller_test_gamepad_id);
    char current_name[160] = {};
    std::snprintf(current_name, sizeof(current_name), "%s (ID %u)",
                  current_name_raw ? current_name_raw : "Controller",
                  static_cast<unsigned>(s_ape_controller_test_gamepad_id));
    if (ImGui::BeginCombo("Controller", current_name)) {
        for (int i = 0; i < count; ++i) {
            const char* raw_name = SDL_GetGamepadNameForID(ids[i]);
            char label[160] = {};
            std::snprintf(label, sizeof(label), "%s (ID %u)",
                          raw_name ? raw_name : "Controller",
                          static_cast<unsigned>(ids[i]));
            if (ImGui::Selectable(label, ids[i] == s_ape_controller_test_gamepad_id)) {
                s_ape_controller_test_gamepad_id = ids[i];
                ape_escape_close_test_gamepad();
                s_ape_controller_test_gamepad_id = ids[i];
            }
        }
        ImGui::EndCombo();
    }

    if (!s_ape_controller_test_gamepad ||
        !SDL_GamepadConnected(s_ape_controller_test_gamepad) ||
        SDL_GetGamepadID(s_ape_controller_test_gamepad) != s_ape_controller_test_gamepad_id) {
        const SDL_JoystickID selected_id = s_ape_controller_test_gamepad_id;
        ape_escape_close_test_gamepad();
        s_ape_controller_test_gamepad = SDL_OpenGamepad(selected_id);
        s_ape_controller_test_gamepad_id = selected_id;
    }
    SDL_free(ids);

    SDL_Gamepad* gamepad = s_ape_controller_test_gamepad;
    if (!gamepad) {
        ImGui::TextColored(col(th.warn), "Could not open controller: %s", SDL_GetError());
        return;
    }

    const float lx = std::max(-1.0f, (float)SDL_GetGamepadAxis(gamepad, SDL_GAMEPAD_AXIS_LEFTX) / 32767.0f);
    const float ly = std::max(-1.0f, (float)SDL_GetGamepadAxis(gamepad, SDL_GAMEPAD_AXIS_LEFTY) / 32767.0f);
    const float rx = std::max(-1.0f, (float)SDL_GetGamepadAxis(gamepad, SDL_GAMEPAD_AXIS_RIGHTX) / 32767.0f);
    const float ry = std::max(-1.0f, (float)SDL_GetGamepadAxis(gamepad, SDL_GAMEPAD_AXIS_RIGHTY) / 32767.0f);
    const float lt = std::max(0.0f, (float)SDL_GetGamepadAxis(gamepad, SDL_GAMEPAD_AXIS_LEFT_TRIGGER) / 32767.0f);
    const float rt = std::max(0.0f, (float)SDL_GetGamepadAxis(gamepad, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER) / 32767.0f);

    if (ImGui::BeginTable("##controller_stick_test", 2, ImGuiTableFlags_SizingStretchSame)) {
        ImGui::TableNextColumn();
        ape_escape_draw_stick_test("##left_stick_test", "LEFT STICK", lx, ly, th);
        ImGui::TableNextColumn();
        ape_escape_draw_stick_test("##right_stick_test", "RIGHT STICK", rx, ry, th);
        ImGui::EndTable();
    }
    ImGui::Text("Triggers: L2 %.0f%%   R2 %.0f%%", std::min(1.0f, lt) * 100.0f,
                std::min(1.0f, rt) * 100.0f);

    const struct { const char* label; SDL_GamepadButton button; } buttons[] = {
        {"SOUTH / CROSS", SDL_GAMEPAD_BUTTON_SOUTH},
        {"EAST / CIRCLE", SDL_GAMEPAD_BUTTON_EAST},
        {"WEST / SQUARE", SDL_GAMEPAD_BUTTON_WEST},
        {"NORTH / TRIANGLE", SDL_GAMEPAD_BUTTON_NORTH},
        {"L1", SDL_GAMEPAD_BUTTON_LEFT_SHOULDER},
        {"R1", SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER},
        {"L3", SDL_GAMEPAD_BUTTON_LEFT_STICK},
        {"R3", SDL_GAMEPAD_BUTTON_RIGHT_STICK},
        {"START", SDL_GAMEPAD_BUTTON_START},
        {"SELECT / BACK", SDL_GAMEPAD_BUTTON_BACK},
        {"DPAD UP", SDL_GAMEPAD_BUTTON_DPAD_UP},
        {"DPAD DOWN", SDL_GAMEPAD_BUTTON_DPAD_DOWN},
        {"DPAD LEFT", SDL_GAMEPAD_BUTTON_DPAD_LEFT},
        {"DPAD RIGHT", SDL_GAMEPAD_BUTTON_DPAD_RIGHT},
    };
    for (size_t i = 0; i < sizeof(buttons) / sizeof(buttons[0]); ++i) {
        const bool down = SDL_GetGamepadButton(gamepad, buttons[i].button);
        char label[96];
        std::snprintf(label, sizeof(label), "%s: %s", buttons[i].label, down ? "PRESSED" : "idle");
        ImGui::PushID(static_cast<int>(i));
        if (down) {
            ImGui::PushStyleColor(ImGuiCol_Button, col(th.accent));
            ImGui::Button(label, ImVec2(px(150.0f), px(28.0f)));
            ImGui::PopStyleColor();
        } else {
            ImGui::Button(label, ImVec2(px(150.0f), px(28.0f)));
        }
        ImGui::PopID();
        if (i % 3u != 2u && i + 1u < sizeof(buttons) / sizeof(buttons[0])) ImGui::SameLine();
    }

    if (ImGui::Button("Test Rumble", ImVec2(px(150.0f), px(32.0f)))) {
        if (SDL_RumbleGamepad(gamepad, 0xBFFFu, 0x5FFFu, 450u)) {
            s_ape_controller_test_status = "Rumble command sent for 450 ms.";
        } else {
            s_ape_controller_test_status = std::string("Rumble unavailable or failed: ") + SDL_GetError();
        }
    }
    if (!s_ape_controller_test_status.empty())
        ImGui::TextWrapped("%s", s_ape_controller_test_status.c_str());
}

/* UPDATE & RELEASE CENTER --------------------------------------------------- */
static void ape_escape_draw_update_release_center(const LauncherTheme& th) {
    if (!ImGui::CollapsingHeader("UPDATE & RELEASE CENTER")) return;
    const std::string info = ape_escape_build_info();
    ImGui::TextWrapped("Installed build: %s", info.c_str());
    ImGui::TextWrapped("The Windows/macOS updater checks this repository's Nightly release and verifies SHA-256 before installation. Linux AppImage updates remain manual.");
    if (ImGui::Button("Check for Nightly Updates", ImVec2(px(220.0f), px(32.0f)))) {
        std::string error;
        const auto safety_snapshot = ape_escape_create_save_backup();
        if (safety_snapshot.empty()) {
            s_ape_update_center_status = "Update check was not started because the automatic safety backup failed.";
        } else if (launch_nvd123_nightly_updater(&error)) {
            s_ape_update_center_status = "Safety backup created. Updater opened; close Ape Escape when asked to install.";
        } else {
            s_ape_update_center_status = error;
        }
    }
    ImGui::SameLine();
    if (ImGui::Button("Open Changelog", ImVec2(px(160.0f), px(32.0f)))) {
        if (!SDL_OpenURL("https://github.com/NVDEMU/ApeEscapeRecomp-MacWindowsLinux/blob/master/CHANGELOG.md"))
            s_ape_update_center_status = "Could not open CHANGELOG.md.";
        else
            s_ape_update_center_status = "Opened the project changelog.";
    }
    if (ImGui::Button("Open Nightly Release", ImVec2(px(190.0f), px(32.0f)))) {
        ape_escape_open_nightly_page();
        s_ape_update_center_status = "Opened the repository's Nightly release page.";
    }
    ImGui::SameLine();
    if (ImGui::Button("Copy Build Information", ImVec2(px(190.0f), px(32.0f)))) {
        ImGui::SetClipboardText(info.c_str());
        s_ape_update_center_status = "Build information copied to the clipboard.";
    }
    if (!s_ape_update_center_status.empty())
        ImGui::TextWrapped("%s", s_ape_update_center_status.c_str());
}
