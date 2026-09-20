/********************************************************************************
 * legacy_ae_summary.sas — SYNTHETIC STUB for public release
 *
 * Mimics the *structure* of a legacy AE-summary report macro (subjects with
 * any AE, then incidence by group term / preferred term per treatment arm)
 * without containing any production logic. Paired with the
 * legacy_ae_summary_report entry in registry_examples/bridge_map_sample.yaml
 * (the AE-SUMMARY-style entry discussed in the manuscript).
 ********************************************************************************/

%macro legacy_ae_summary(
    population_from  = ,          /* population dataset (denominators)   */
    population_where = ,          /* subsetting WHERE clause             */
    observation_from = ,          /* adverse-event dataset               */
    observation_where= ,          /* AE subsetting WHERE clause          */
    ae_term_selection= ,          /* preferred-term selection variable   */
    grp_term_selection=,          /* group-term selection variable       */
    therapy_cd_var   = TRTCD,     /* treatment code variable             */
    therapy_des_var  = TRTDES,    /* treatment description variable      */
    aetrt_cd_var     = AETRTCD,   /* AE-level treatment code variable    */
    aetrt_des_var    = AETRTDES,  /* AE-level treatment description      */
    display_totals   = Y,         /* Y = include "any AE" summary rows   */
    display_term_row = Y,         /* Y = include preferred-term rows     */
    percent_incidence= Y,         /* Y = append (%) to each count        */
    decimal_places_percent = 1,   /* decimals for percentages            */
    create_output_dataset = N,    /* Y = keep the summary dataset        */
    output_fileref   = fptotb,    /* fileref for the RTF destination     */
    output_data      = work._ae_out,    /* incidence dataset             */
    rel_col_widths   = ,          /* relative column widths for display  */
    page_orientation = P,         /* P = portrait, L = landscape         */
    font_size        = 8,
    title_text_1     = ,
    title_text_2     = ,
    subtitle         = ,
    end_notes        = ,
    data_source_txt  = ,
    debug            = N
);

    /* --- subject-level incidence by group term / preferred term ----------- */
    proc sql;
        create table &output_data. as
        select &grp_term_selection. as grp_term,
               &ae_term_selection.  as ae_term,
               &therapy_cd_var.,
               count(distinct subjid) as n_subj
        from &observation_from.
        %if %length(&observation_where.) > 0 %then
            where &observation_where.;
        group by grp_term, ae_term, &therapy_cd_var.;
    quit;

    /* --- render to the ODS RTF destination -------------------------------- */
    ods rtf file=&output_fileref.;
    title1 "&title_text_1.";
    title2 "&title_text_2.";
    title3 "&subtitle.";
    footnote1 "&end_notes.";
    footnote2 "&data_source_txt.";

    proc report data=&output_data. nowd;
        column grp_term ae_term &therapy_cd_var. n_subj;
        define grp_term / group order;
        define ae_term  / group order;
        define n_subj   / "n";
    run;

    ods rtf close;

    %if %upcase(&create_output_dataset.) ne Y %then %do;
        proc datasets library=work nolist; delete _ae_out; quit;
    %end;

    %if %upcase(&debug.) = Y %then %do;
        proc print data=&output_data.; run;
    %end;

%mend legacy_ae_summary;
