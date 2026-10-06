# GraphQL query constants for Horizon API

# Base pentest fields that are always included
PENTEST_BASE_FIELDS = """
    op_id
    op_type
    name
    state
    user_name
    client_name
    min_scope
    max_scope
    exclude_scope
    scheduled_at
    launched_at
    completed_at
    canceled_at
    etl_completed_at
    duration_s
    impacts_count
    impact_paths_count
    attack_paths_count
    phished_impact_paths_count
    phished_attack_paths_count
    weakness_types_count
    weaknesses_count
    hosts_count
    out_of_scope_hosts_count
    external_domains_count
    services_count
    credentials_count
    users_count
    cred_access_count
    data_stores_count
    websites_count
    data_resources_count
    nodezero_script_url
    nodezero_ip
"""

# Attack paths fields
ATTACK_PATHS_FIELDS = """
    attack_paths_page {
        page_info {
            page_size
            end_cursor
        }
        attack_paths {
            uuid
            impact_type
            impact_title
            impact_description
            name
            attack_path_title
            base_score
            score
            severity
            context_score_description_md
            op_id
            weakness_refs
            credential_refs
            host_refs
            time_to_finding_hms
            time_to_finding_s
            created_at
            target_entity_text
            affected_asset_text
            ip
            host_name
            host_text
        }
    }
"""

# Weaknesses fields
WEAKNESSES_FIELDS = """
    weaknesses_page {
        page_info {
            page_size
            end_cursor
        }
        weaknesses {
            uuid
            created_at
            vuln_id
            vuln_aliases
            vuln_category
            vuln_name
            vuln_short_name
            vuln_cisa_kev
            vuln_known_ransomware_campaign_use
            op_id
            ip
            has_proof
            proof_failure_code
            proof_failure_reason
            score
            severity
            base_score
            base_severity
            context_score
            context_severity
            context_score_description_md
            context_score_description
            time_to_finding_hms
            time_to_finding_s
            affected_asset_text
            downstream_impact_types
            downstream_impact_types_and_counts
            impact_paths_count
            attack_paths_count
            diff_status
            mitre_mappings {
                mitre_tactic_id
                mitre_technique_id
                mitre_subtechnique_id
            }
        }
    }
"""

# Query for getting pentests
PENTESTS_QUERY = """
query pentests_page($page_input: PageInput) {
    pentests_page(page_input: $page_input) {
        pentests {
            %s
        }
        page_info {
            page_size
            end_cursor
        }
    }
}
"""

# Query for getting attack paths
ATTACK_PATHS_QUERY = """
query attack_paths_page($input: OpInput!, $page_input: PageInput) {
  attack_paths_page(input: $input, page_input: $page_input) {
    attack_paths {
        uuid
        impact_type
        impact_title
        impact_description
        name
        attack_path_title
        base_score
        score
        severity
        context_score_description_md
        op_id
        weakness_refs
        credential_refs
        host_refs
        time_to_finding_hms
        time_to_finding_s
        created_at
        target_entity_text
        affected_asset_text
        ip
        host_name
        host_text
    }
    page_info {
        page_size
        end_cursor
    }
  }
}
"""

# Query for getting weaknesses
WEAKNESSES_QUERY = """
query weaknesses_page($input: OpInput!, $page_input: PageInput) {
    weaknesses_page(input: $input, page_input: $page_input) {
        weaknesses {
            uuid
            created_at
            vuln_id
            vuln_aliases
            vuln_category
            vuln_name
            vuln_short_name
            vuln_cisa_kev
            vuln_known_ransomware_campaign_use
            op_id
            ip
            has_proof
            proof_failure_code
            proof_failure_reason
            score
            severity
            base_score
            base_severity
            context_score
            context_severity
            context_score_description_md
            context_score_description
            time_to_finding_hms
            time_to_finding_s
            affected_asset_text
            downstream_impact_types
            downstream_impact_types_and_counts
            impact_paths_count
            attack_paths_count
            diff_status
            mitre_mappings {
                mitre_tactic_id
                mitre_technique_id
                mitre_subtechnique_id
            }
        }
        page_info {
            page_size
            end_cursor
        }
    }
}
"""
